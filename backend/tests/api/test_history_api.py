"""Confirmation HTTP privacy, scoped cookies, receipts and persistent rejection limits."""
from uuid import UUID, uuid4
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from app.api.v1.endpoints.auth import current_user
from app.api.v1.endpoints.history import optional_customer
from app.core.config import get_settings
from app.core.history_http import history_guard
from app.db.session import get_db_session
from app.main import app
from app.models.domain import User
from app.models.history import ConfirmationRequest


@pytest_asyncio.fixture
async def history_api(session, worker, monkeypatch):
    actor_id = worker.user_id
    async def db():
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
    async def actor():
        return await session.get(User, actor_id)
    async def guest_actor():
        return None
    async def guard():
        pass
    monkeypatch.setattr(get_settings(), "sms_provider", "stub")
    monkeypatch.setattr(get_settings(), "environment", "development")
    app.dependency_overrides.update({get_db_session: db, current_user: actor, optional_customer: guest_actor, history_guard: guard})
    await session.commit()
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            yield client
    finally:
        app.dependency_overrides.clear()


async def invite(client):
    claim = await client.post("/api/v1/me/history-claims", headers={"Idempotency-Key": str(uuid4())}, json={"details": {"work_type": "Plumbing", "description": "Repaired pipe for ₦5000", "language": "en"}})
    assert claim.status_code == 201, claim.text
    operation = str(uuid4())
    response = await client.post(f"/api/v1/me/history-claims/{claim.json()['id']}/confirmation-requests", headers={"Idempotency-Key": operation}, json={"revision": 1, "recipient_phone": "+2348012345678"})
    assert response.status_code == 201, response.text
    return claim.json(), response.json(), operation


async def test_link_does_not_disclose_claim_and_cookie_is_request_scoped(history_api, session):
    client = history_api
    claim, request, op = await invite(client)
    base = f"/api/v1/history-confirmations/{request['token']}"
    result = await client.get(base)
    assert result.status_code == 200 and result.json()["details"] is None
    assert result.json()["masked_phone"] == "••••5678"
    assert "+2348012345678" not in result.text
    assert result.headers["cache-control"] == "no-store, private"
    assert result.headers["referrer-policy"] == "no-referrer"
    assert result.headers["x-robots-tag"] == "noindex, nofollow"
    blocked = await client.post(base+"/response", headers={"Idempotency-Key": str(uuid4())}, json={"decision": "confirmed", "declares_customer": True, "consent": True})
    assert blocked.status_code == 403
    challenge = await client.post(base+"/challenge")
    assert challenge.json()["sandbox"] and challenge.json()["debug_code"]
    check = await client.post(base+"/challenge/check", json={"code": challenge.json()["debug_code"]})
    assert check.status_code == 200
    assert "HttpOnly" in check.headers["set-cookie"] and "Path=/api/v1/history-confirmations" in check.headers["set-cookie"]
    checked = (await client.get(base)).json()
    assert checked["details"]["description"] == claim["details"]["description"]
    assert checked["attribution"] == "contact_verified" and checked["response"] is None
    _, other, _ = await invite(client)
    assert (await client.get(f"/api/v1/history-confirmations/{other['token']}")).json()["access"] == "contact_required"
    receipt = await client.get(f"/api/v1/me/history-claims/{claim['id']}/confirmation-requests/operations/{op}")
    assert receipt.json()["token"] is None


async def test_response_receipt_replay_withdrawal_and_revision(history_api):
    client = history_api
    claim, request, _ = await invite(client)
    base = f"/api/v1/history-confirmations/{request['token']}"
    code = (await client.post(base+"/challenge")).json()["debug_code"]
    assert (await client.post(base+"/challenge/check", json={"code": code})).status_code == 200
    payload = {"decision": "confirmed", "declares_customer": True, "consent": True}
    headers = {"Idempotency-Key": str(uuid4())}
    first = await client.post(base+"/response", json=payload, headers=headers)
    assert first.status_code == 200 and first.json()["sandbox"]
    assert (await client.post(base+"/response", json=payload, headers=headers)).json() == first.json()
    duplicate = await client.post(base+"/response", json=payload, headers={"Idempotency-Key": str(uuid4())})
    assert duplicate.status_code == 409 and duplicate.json()["code"] == "RESPONSE_EXISTS"
    assert (await client.get(base)).json()["response"]["id"] == first.json()["id"]
    assert (await client.delete(base+"/response")).status_code == 204
    assert (await client.get(base)).json()["response"]["withdrawn_at"]
    edit = await client.patch(f"/api/v1/me/history-claims/{claim['id']}", json={"revision": 1, "details": {**claim["details"], "description": "Corrected description"}})
    assert edit.status_code == 200 and edit.json()["response"] is None
    assert (await client.get(base)).status_code == 410


async def test_bad_codes_are_committed_and_errors_do_not_echo_input(history_api, session):
    client = history_api
    _, request, _ = await invite(client)
    base = f"/api/v1/history-confirmations/{request['token']}"
    code = (await client.post(base+"/challenge")).json()["debug_code"]
    bad = "111111" if code != "111111" else "222222"
    for _ in range(5):
        response = await client.post(base+"/challenge/check", json={"code": bad})
        assert response.status_code == 400 and response.json()["code"] == "CODE_INVALID"
    session.expire_all()
    row = await session.get(ConfirmationRequest, UUID(request["id"]))
    assert row.challenge_attempts == 5
    assert (await client.post(base+"/challenge/check", json={"code": code})).json()["code"] == "CHALLENGE_UNAVAILABLE"
    invalid = await client.post(base+"/challenge/check", json={"code": "sensitive-do-not-echo"})
    assert invalid.status_code == 422 and "sensitive-do-not-echo" not in invalid.text
    assert (await client.get("/api/v1/me/history-claims?size=101")).status_code == 422


async def test_integrated_counts_sharing_and_credential_exclusion(history_api, session, worker, monkeypatch):
    client = history_api
    worker_id = str(worker.id)
    monkeypatch.setattr(get_settings(), "credential_signing_secret", "history-test-secret-"*3)
    before = (await client.get("/api/v1/me/record")).json()
    claim, request, _ = await invite(client)
    base = f"/api/v1/history-confirmations/{request['token']}"
    code = (await client.post(base+"/challenge")).json()["debug_code"]
    await client.post(base+"/challenge/check", json={"code": code})
    response = await client.post(base+"/response", headers={"Idempotency-Key":str(uuid4())}, json={"decision":"confirmed", "declares_customer":True, "consent":True})
    assert response.status_code == 200
    operation = str(uuid4())
    message = await client.post(base+"/messages", headers={"Idempotency-Key":operation}, json={"text":"Private conversation: do not expose this", "language":"en"})
    assert message.status_code == 201
    receipt = await client.get(base+f"/messages/operations/{operation}")
    assert receipt.json()["id"] == message.json()["id"]
    after = (await client.get("/api/v1/me/record")).json()
    assert after["assessment"] == before["assessment"]
    assert after["informal_history"]["declared_jobs"] == 1
    assert after["informal_history"]["sandbox_attested_jobs"] == 1
    assert after["informal_history"]["contact_attested_jobs"] == 0
    share = await client.post("/api/v1/me/worker/shares", headers={"Idempotency-Key":str(uuid4())})
    assert share.status_code == 201
    public_path = f"/api/v1/verification/{share.json()['token']}"
    summary = await client.get(public_path)
    assert summary.status_code == 200 and summary.json()["informal_history"] == after["informal_history"]
    for private in ("+2348012345678", "Private conversation", claim["details"]["description"], request["token"]):
        assert private not in summary.text
    assert len(summary.content) < 20_000
    exported = await client.get(f"/api/v1/workers/{worker_id}/credentials/export")
    assert exported.status_code == 200 and exported.json()["verified_outcomes"] == []
    await client.delete(f"/api/v1/me/worker/shares/{share.json()['id']}")
    assert (await client.get(public_path)).status_code == 410


def test_history_openapi_describes_distinct_authorization():
    schema = app.openapi()
    paths = schema["paths"]
    assert paths["/api/v1/me/history-claims"]["post"]["security"] == [{"UserSession":[]}]
    assert paths["/api/v1/history-confirmations/{token}/challenge"]["post"]["security"] == []
    assert paths["/api/v1/history-confirmations/{token}/messages"]["get"]["security"] == [{"HistoryRecipient":[]}, {"UserSession":[]}]
    assert "HistoryRecipient" in schema["components"]["securitySchemes"]


async def test_history_job_choices_have_paginated_contract(history_api):
    response = await history_api.get("/api/v1/me/history-jobs?page=1&size=20")
    assert response.status_code == 200, response.text
    body = response.json()
    assert isinstance(body["items"], list)
    assert body["page"] == 1
    assert body["size"] == 20
    assert isinstance(body["pages"], int)
    assert isinstance(body["total"], int)


async def test_clarification_requires_current_confirmation_request(history_api):
    response = await history_api.post("/api/v1/me/history-claims", headers={"Idempotency-Key": str(uuid4())}, json={"details": {"work_type": "Plumbing", "description": "Repaired pipe", "language": "en"}})
    assert response.status_code == 201, response.text
    base = f"/api/v1/me/history-claims/{response.json()['id']}/messages"
    listing = await history_api.get(base)
    assert listing.status_code == 409
    assert listing.json()["code"] == "THREAD_UNAVAILABLE"
    sending = await history_api.post(base, headers={"Idempotency-Key": str(uuid4())}, json={"text": "Please check the details", "language": "en"})
    assert sending.status_code == 409
    assert sending.json()["code"] == "THREAD_UNAVAILABLE"


async def test_private_audio_requires_contact_and_blocks_revoked_request(history_api, session, monkeypatch, tmp_path):
    from datetime import timedelta
    from app.models.history import HistoryMessage, MessageTranslation, MessageAudio
    from app.services.feature_common import now
    from app.services.history_speech import fingerprint
    from app.services.history_drafts import _write_audio
    monkeypatch.setattr(get_settings(), 'history_audio_dir', str(tmp_path))
    client = history_api
    claim, request, _ = await invite(client)
    message = HistoryMessage(request_id=UUID(request['id']), actor_role='worker', operation_id=uuid4(), payload_hash='test', language='en', text='Check the date')
    session.add(message); await session.flush()
    tr = MessageTranslation(message_id=message.id, target='yo', status='ready', text='Ṣàyẹ̀wò ọjọ́', model='N-ATLAS', model_revision='test')
    session.add(tr); await session.flush()
    audio = MessageAudio(translation_id=tr.id, fingerprint=fingerprint(tr), language='yo', status='ready', provider_model='test', provider_version='1', audio_path=str(_write_audio(b'ID3test')), expires_at=now()+timedelta(hours=24))
    session.add(audio); await session.commit()
    base = f"/api/v1/history-confirmations/{request['token']}"
    path = f"{base}/messages/{message.id}/audio/{audio.id}/content"
    assert (await client.get(path)).status_code == 403
    code = (await client.post(base+'/challenge')).json()['debug_code']
    assert (await client.post(base+'/challenge/check', json={'code': code})).status_code == 200
    response = await client.get(path)
    assert response.status_code == 200
    assert response.content == b'ID3test'
    assert response.headers['cache-control'] == 'no-store, private'
    assert response.headers['content-type'] == 'audio/mpeg'
    assert (await client.delete(f"/api/v1/me/confirmation-requests/{request['id']}")).status_code == 204
    assert (await client.get(path)).status_code == 410


async def test_serverless_external_voice_capabilities(history_api, monkeypatch):
    cfg = get_settings()
    monkeypatch.setattr(cfg, "deployment_mode", "serverless")
    monkeypatch.setattr(cfg, "history_ai_enabled", True)
    monkeypatch.setattr(cfg, "history_ai_base_url", "https://model.test")
    monkeypatch.setattr(cfg, "history_external_worker", True)
    monkeypatch.setattr(cfg, "history_audio_storage", "s3")
    monkeypatch.setattr(cfg, "history_audio_bucket", "private-audio")
    import app.api.v1.endpoints.history as endpoint
    monkeypatch.setattr(endpoint.shutil, "which", lambda name: None)
    response = await history_api.get("/api/v1/me/history-capabilities")
    assert response.status_code == 200
    assert response.json()["voice_configured"] is True
    assert response.json()["audio_max_bytes"] == 3 * 1024 * 1024
