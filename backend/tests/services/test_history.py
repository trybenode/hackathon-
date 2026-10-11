"""Real persistence tests for attribution boundaries and assessment isolation."""
from datetime import timedelta
from uuid import uuid4
import pytest
from sqlalchemy import select, func
from app.core.config import get_settings
from app.models.domain import User, Job, JobStatus, JobType, Organization, OrganizationType, NormalizedOutcome
from app.models.history import HistoryClaim, ConfirmationRequest
from app.schemas.history import ClaimCreate, ClaimDetails, ClaimEdit, RequestCreate, CustomerDecision
from app.services import history
from app.services.portability import FeatureError, now
from app.services.trust_scoring.assessment import assess_worker


@pytest.fixture(autouse=True)
def local_contact(monkeypatch):
    cfg = get_settings()
    monkeypatch.setattr(cfg, "environment", "development")
    monkeypatch.setattr(cfg, "sms_provider", "stub")


async def setup_claim(session, worker):
    user = await session.get(User, worker.user_id)
    data = ClaimCreate(details=ClaimDetails(work_type="Cleaning", description="Cleaned a house", date_text="last month", language="yo"))
    claim = await history.create_claim(session, user, data, uuid4())
    invite = await history.issue_request(session, user, claim.id, RequestCreate(revision=1, recipient_phone="+2348012345678"), uuid4())
    await session.commit()
    return user, claim, invite


async def guest_session(session, token):
    sandbox, code = await history.start_challenge(session, token)
    assert sandbox and code
    secret = await history.check_challenge(session, token, code)
    await session.commit()
    return secret


async def test_contact_required_and_score_isolation(session, worker):
    before = await assess_worker(session, worker.id, "generic")
    user, claim, invite = await setup_claim(session, worker)
    row, stored = await history.lookup_request(session, invite.token)
    with pytest.raises(FeatureError, match="Verify"):
        await history.authorize(session, row, stored, None, invite.token)
    guest = await guest_session(session, invite.token)
    payload = CustomerDecision(decision="confirmed", declares_customer=True, consent=True)
    operation = uuid4()
    result = await history.submit_response(session, invite.token, None, guest, payload, operation, "127.0.0.1", "test")
    await session.commit()
    assert result.sandbox and result.attribution == "contact_verified_relationship_declared"
    assert (await history.submit_response(session, invite.token, None, guest, payload, operation, "x", "x")).id == result.id
    with pytest.raises(FeatureError) as error:
        await history.submit_response(session, invite.token, None, guest, payload, uuid4(), "x", "x")
    assert error.value.code == "RESPONSE_EXISTS"
    counts = await history.history_counts(session, worker.id)
    assert counts.declared_jobs == 1 and counts.sandbox_attested_jobs == 1 and counts.contact_attested_jobs == 0
    after = await assess_worker(session, worker.id, "generic")
    assert before.id == after.id
    assert await session.scalar(select(func.count()).select_from(NormalizedOutcome)) == 0


async def test_edit_revoke_archive_and_stale_revision(session, worker):
    user, claim, invite = await setup_claim(session, worker)
    guest = await guest_session(session, invite.token)
    row = await history.edit_claim(session, user, claim.id, ClaimEdit(revision=1, details=ClaimDetails(work_type="Cleaner", description="Corrected job")))
    assert row.revision == 2
    await session.commit()
    with pytest.raises(FeatureError) as error:
        await history.lookup_request(session, invite.token)
    assert error.value.status == 410
    with pytest.raises(FeatureError):
        await history.edit_claim(session, user, claim.id, ClaimEdit(revision=1, details=row.details))
    await history.archive_claim(session, user, claim.id)
    assert (await history.claims(session, user, 1, 20)).total == 0


async def test_challenge_expiry_wrong_codes_and_production_stub(session, worker, monkeypatch):
    _, _, invite = await setup_claim(session, worker)
    _, code = await history.start_challenge(session, invite.token)
    bad = "000000" if code != "000000" else "111111"
    for _ in range(5):
        with pytest.raises(FeatureError) as error:
            await history.check_challenge(session, invite.token, bad)
        assert error.value.code == "CODE_INVALID"
    with pytest.raises(FeatureError) as error:
        await history.check_challenge(session, invite.token, code)
    assert error.value.code == "CHALLENGE_UNAVAILABLE"
    row, _ = await history.lookup_request(session, invite.token)
    row.challenge_sent_at = now()-timedelta(minutes=2)
    monkeypatch.setattr(get_settings(), "environment", "production")
    with pytest.raises(FeatureError) as error:
        await history.start_challenge(session, invite.token)
    assert error.value.code == "CONTACT_PROVIDER_UNAVAILABLE"


async def test_wrong_guest_and_ownership(session, worker):
    _, claim, invite = await setup_claim(session, worker)
    guest = await guest_session(session, invite.token)
    row, stored = await history.lookup_request(session, invite.token)
    with pytest.raises(FeatureError):
        await history.authorize(session, row, stored, None, guest+"wrong")
    stranger = User(email="stranger@test.example", display_name="Other")
    session.add(stranger); await session.flush()
    with pytest.raises(FeatureError):
        await history.owned_claim(session, stranger, claim.id)


async def test_system_customer_matching_and_canonical_fields(session, worker):
    user = await session.get(User, worker.user_id)
    customer = User(email="client@test.example", display_name="Client")
    org = Organization(name="Direct", organization_type=OrganizationType.PLATFORM)
    session.add_all([customer, org]); await session.flush()
    job = Job(worker_id=worker.id, client_id=customer.id, organization_id=org.id, title="Authoritative title", agreed_amount=100, job_type=JobType.INDEPENDENT, status=JobStatus.COMPLETED)
    session.add(job); await session.flush()
    claim = await history.create_claim(session, user, ClaimCreate(job_id=job.id, details=ClaimDetails(work_type="Fake", description="Notes", date_text="invented")), uuid4())
    assert claim.details.work_type == job.title and claim.details.date_text is None
    invite = await history.issue_request(session, user, claim.id, RequestCreate(revision=1), uuid4())
    row, stored = await history.lookup_request(session, invite.token)
    assert await history.authorize(session, row, stored, customer, None) == ("matched_hiring_account", False)
    with pytest.raises(FeatureError):
        await history.authorize(session, row, stored, user, None)
    with pytest.raises(FeatureError):
        await history.start_challenge(session, invite.token)


async def test_idempotency_and_request_receipts(session, worker):
    user = await session.get(User, worker.user_id)
    data = ClaimCreate(details=ClaimDetails(work_type="Cleaning", description="Job"))
    op = uuid4()
    a = await history.create_claim(session, user, data, op)
    assert (await history.create_claim(session, user, data, op)).id == a.id
    with pytest.raises(FeatureError):
        await history.create_claim(session, user, ClaimCreate(details=ClaimDetails(work_type="Different", description="Job")), op)
    req_op = uuid4()
    payload = RequestCreate(revision=1, recipient_phone="+2348012345678")
    invite = await history.issue_request(session, user, a.id, payload, req_op)
    assert invite.token
    retry = await history.issue_request(session, user, a.id, payload, req_op)
    assert retry.id == invite.id and retry.token is None
    page = await history.request_list(session, user, a.id, 1, 20)
    assert page.items[0].token is None


async def test_unrecognized_response_never_claims_declared_relationship(session, worker):
    _, _, invite = await setup_claim(session, worker)
    guest = await guest_session(session, invite.token)
    response = await history.submit_response(session, invite.token, None, guest, CustomerDecision(decision="unrecognized", declares_customer=False, consent=True), uuid4(), "test", "test")
    assert response.attribution == "contact_verified" and not response.declares_customer
    counts = await history.history_counts(session, worker.id)
    assert counts.sandbox_attested_jobs == 0 and counts.contact_attested_jobs == 0
