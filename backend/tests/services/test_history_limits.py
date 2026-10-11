"""Abuse limits and provider contracts without sending SMS or using shared services."""
from datetime import timedelta
from uuid import uuid4
import os
import pytest
from redis.asyncio import Redis as RealRedis
from starlette.requests import Request
from sqlalchemy.ext.asyncio import async_sessionmaker
from app.core import history_http
from app.core.config import get_settings
from app.models.domain import User
from app.schemas.history import ClaimCreate, ClaimDetails, RequestCreate, CustomerDecision
from app.services import history
from app.services.contact_provider import TwilioContactProvider
from app.services.portability import FeatureError, now


async def request_for(session, worker):
    user = await session.get(User, worker.user_id)
    claim = await history.create_claim(session, user, ClaimCreate(details=ClaimDetails(work_type="Cleaner", description="House")), uuid4())
    invite = await history.issue_request(session, user, claim.id, RequestCreate(revision=1, recipient_phone="+2348012345678"), uuid4())
    await session.commit()
    return user, invite


async def test_five_sms_sends_and_replay_guard(session, worker, monkeypatch):
    cfg = get_settings()
    monkeypatch.setattr(cfg, "environment", "development"); monkeypatch.setattr(cfg, "sms_provider", "stub")
    _, invite = await request_for(session, worker)
    for _ in range(5):
        _, code = await history.start_challenge(session, invite.token)
        row, _ = await history.lookup_request(session, invite.token)
        row.challenge_sent_at = now()-timedelta(minutes=2)
    with pytest.raises(FeatureError) as error:
        await history.start_challenge(session, invite.token)
    assert error.value.code == "CHALLENGE_SEND_LIMIT"
    await history.check_challenge(session, invite.token, code)
    with pytest.raises(FeatureError) as error:
        await history.check_challenge(session, invite.token, code)
    assert error.value.code == "CHALLENGE_UNAVAILABLE"


async def test_sms_provider_checks_exact_stored_reference(monkeypatch):
    cfg = get_settings()
    for key, value in {"twilio_account_sid":"AC"+"a"*32, "twilio_auth_token":"test-not-real", "twilio_verify_service_sid":"VA"+"b"*32}.items():
        monkeypatch.setattr(cfg, key, value)
    provider = TwilioContactProvider()
    calls = []
    reference = "VE"+"c"*32
    async def post(path, data):
        calls.append((path, data))
        return {"sid": reference, "to": "+2348012345678", "status": "approved"}
    monkeypatch.setattr(provider, "_post", post)
    assert (await provider.send("+2348012345678")).reference == reference
    assert await provider.check("+2348012345678", "123456", reference)
    assert calls[-1][1] == {"VerificationSid": reference, "Code": "123456"}
    assert not await provider.check("+2348012345678", "123456", "VE"+"d"*32)


def browser_request(origin="http://localhost:3000", cookie=None):
    headers = [(b"origin", origin.encode())]
    if cookie:
        headers.append((b"cookie", f"history_recipient={cookie}".encode()))
    return Request({"type":"http", "method":"POST", "path":"/api/v1/history-confirmations/redacted/challenge", "headers":headers, "client":("127.0.0.9",1234)})


async def test_origin_and_redacted_limit_keys(monkeypatch):
    monkeypatch.setattr(get_settings(), "history_enabled", True)
    with pytest.raises(FeatureError) as error:
        await history_http.history_guard(browser_request("https://untrusted.example"))
    assert error.value.code == "ORIGIN_REJECTED"
    recorded = []
    class Limiter:
        @classmethod
        def from_url(cls, *args, **kwargs):
            return cls()
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass
        async def eval(self, script, number, *keys):
            recorded.extend(keys)
            return [1,6]
    monkeypatch.setattr(history_http, "Redis", Limiter)
    with pytest.raises(FeatureError) as error:
        await history_http.history_guard(browser_request(cookie="private-contact-cookie"))
    assert error.value.code == "HISTORY_RATE_LIMIT"
    assert all("private-contact-cookie" not in key and "127.0.0.9" not in key for key in recorded)


@pytest.mark.skipif(not os.environ.get("TEST_DATABASE_URL", "").startswith("postgresql"), reason="Needs isolated PostgreSQL")
async def test_concurrent_customer_responses_are_serialized(session, worker, monkeypatch):
    import asyncio
    cfg = get_settings()
    monkeypatch.setattr(cfg, "environment", "development"); monkeypatch.setattr(cfg, "sms_provider", "stub")
    _, invite = await request_for(session, worker)
    _, code = await history.start_challenge(session, invite.token)
    guest = await history.check_challenge(session, invite.token, code)
    await session.commit()
    factory = async_sessionmaker(session.bind, expire_on_commit=False)
    async def respond():
        async with factory() as independent:
            try:
                result = await history.submit_response(independent, invite.token, None, guest, CustomerDecision(decision="confirmed", declares_customer=True, consent=True), uuid4(), "test", "test")
                await independent.commit()
                return result.decision
            except FeatureError as error:
                await independent.rollback()
                return error.code
    assert sorted(await asyncio.gather(respond(), respond())) == ["RESPONSE_EXISTS", "confirmed"]


@pytest.mark.skipif(not os.environ.get("TEST_REDIS_URL"), reason="Needs isolated Redis")
async def test_live_history_limiter(monkeypatch):
    import secrets
    from app.services.portability import digest
    cfg = get_settings(); monkeypatch.setattr(cfg, "redis_url", os.environ["TEST_REDIS_URL"]); monkeypatch.setattr(cfg, "history_enabled", True)
    cookie = "integration-"+secrets.token_hex(16)
    request = browser_request(cookie=cookie)
    request.scope["client"] = ("history-test-"+secrets.token_hex(8), 1234)
    bucket = int(now().timestamp())//60
    keys = [f"history:ip:{digest(request.client.host)}:{bucket}", f"history:actor:{digest(cookie)}:{bucket}"]
    try:
        for _ in range(5):
            await history_http.history_guard(request)
        with pytest.raises(FeatureError) as error:
            await history_http.history_guard(request)
        assert error.value.code == "HISTORY_RATE_LIMIT"
    finally:
        async with RealRedis.from_url(cfg.redis_url) as client:
            await client.delete(*keys)


async def test_persisted_sandbox_access_never_authorizes_production(session, worker, monkeypatch):
    cfg = get_settings()
    monkeypatch.setattr(cfg, "environment", "development"); monkeypatch.setattr(cfg, "sms_provider", "stub")
    _, invite = await request_for(session, worker)
    _, code = await history.start_challenge(session, invite.token)
    guest = await history.check_challenge(session, invite.token, code)
    await session.commit()
    monkeypatch.setattr(cfg, "environment", "production")
    row, claim = await history.lookup_request(session, invite.token)
    with pytest.raises(FeatureError) as error:
        await history.authorize(session, row, claim, None, guest)
    assert error.value.code == "CONTACT_VERIFICATION_REQUIRED"
