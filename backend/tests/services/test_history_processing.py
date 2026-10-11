"""Inference failure, approval, private clarification and stale attribution regressions."""
from datetime import timedelta
from uuid import uuid4
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker
from app.core.config import get_settings
from app.models.domain import User, Job, JobStatus, JobType, Organization, OrganizationType, NormalizedOutcome
from app.models.history import HistoryDraft, HistoryClaim
from app.schemas.history import ClaimCreate, ClaimDetails, RequestCreate, CustomerDecision, DraftApproval, MessageCreate
from app.services import history, history_drafts, history_messages
from app.services.customer_evidence import UnavailableCustomerEvidence
from app.services.history_ai import HistoryModelGateway, LLM_MODEL
from app.services.portability import FeatureError, now


@pytest.fixture
def processing_config(monkeypatch, tmp_path):
    cfg = get_settings()
    monkeypatch.setattr(cfg, "environment", "development")
    monkeypatch.setattr(cfg, "history_ai_enabled", True)
    monkeypatch.setattr(cfg, "history_ai_base_url", "http://model.test")
    monkeypatch.setattr(cfg, "history_audio_dir", str(tmp_path))
    return tmp_path


async def test_voice_queue_approval_is_required_and_idempotent(session, worker, processing_config, monkeypatch):
    user = await session.get(User, worker.user_id)
    operation = uuid4()
    draft = await history_drafts.enqueue(session, user, b"fixture-audio", "yo", None, operation)
    assert draft.status == "queued" and draft.details is None
    assert (await history_drafts.enqueue(session, user, b"fixture-audio", "yo", None, operation)).id == draft.id
    with pytest.raises(FeatureError):
        await history_drafts.enqueue(session, user, b"changed", "yo", None, operation)
    with pytest.raises(FeatureError):
        await history_drafts.approve(session, user, draft.id, DraftApproval(details=ClaimDetails(work_type="Plumbing", description="Fixture"), approved=True))
    await session.commit()
    async def normalize(path):
        return path
    async def transcribe(self, audio, language):
        return "Fixture transcript", {"asr": "test-fixture", "revision": "test"}
    async def extract(self, transcript, language):
        return ClaimDetails(work_type="Plumbing", description="Fixture", language=language)
    monkeypatch.setattr(history_drafts, "normalize_audio", normalize)
    monkeypatch.setattr(HistoryModelGateway, "transcribe", transcribe)
    monkeypatch.setattr(HistoryModelGateway, "extract", extract)
    factory = async_sessionmaker(session.bind, expire_on_commit=False)
    assert await history_drafts.process_one(factory)
    user_id = user.id
    session.expire_all()
    user = await session.get(User, user_id)
    await session.refresh(worker)
    row = await history_drafts.owned_draft(session, user, draft.id)
    assert row.status == "ready" and row.transcript == "Fixture transcript"
    assert await session.scalar(select(func.count()).select_from(HistoryClaim)) == 0
    payload = DraftApproval(details=ClaimDetails.model_validate(row.details), approved=True)
    saved = await history_drafts.approve(session, user, draft.id, payload)
    assert (await history_drafts.approve(session, user, draft.id, payload)).id == saved.id
    await session.commit()
    assert not list(processing_config.glob("*.upload"))
    assert await session.scalar(select(func.count()).select_from(NormalizedOutcome)) == 0
    assert row.transcript is None and row.status == "saved"


async def test_audio_ownership_expiry_and_exhausted_leases(session, worker, processing_config):
    user = await session.get(User, worker.user_id)
    with pytest.raises(FeatureError) as error:
        await history_drafts.enqueue(session, user, b"audio", "en", uuid4(), uuid4())
    assert error.value.code == "JOB_NOT_FOUND" and not list(processing_config.iterdir())
    draft = await history_drafts.enqueue(session, user, b"audio", "en", None, uuid4())
    row = await session.get(HistoryDraft, draft.id)
    row.status = "processing"; row.attempts = 3; row.lease_until = now()-timedelta(seconds=1)
    await history_drafts.sweep(session)
    assert row.status == "failed" and row.error_code == "AUDIO_RETRY_EXHAUSTED"
    row.expires_at = now()-timedelta(seconds=1); row.transcript = "Private"
    await history_drafts.sweep(session)
    assert row.status == "expired" and row.transcript is None and row.audio_path is None
    assert not list(processing_config.glob("*.upload"))


async def test_translation_preserves_original_and_rejects_changed_values(processing_config, monkeypatch):
    async def altered(self, path, **kwargs):
        return {"model": LLM_MODEL, "text": "Pay ₦6000 on 2026-10-01"}
    monkeypatch.setattr(HistoryModelGateway, "_call", altered)
    with pytest.raises(FeatureError) as error:
        await HistoryModelGateway().translate("Do not pay ₦5000 on 2026-10-01", "en", "yo")
    assert error.value.code == "TRANSLATION_VALUES_CHANGED"
    assert await HistoryModelGateway().translate("Do not pay ₦5000", "en", "en") == "Do not pay ₦5000"


async def test_clarification_retry_privacy_and_translation_failure(session, worker, processing_config, monkeypatch):
    user = await session.get(User, worker.user_id)
    claim = await history.create_claim(session, user, ClaimCreate(details=ClaimDetails(work_type="Cleaner", description="Work")), uuid4())
    invite = await history.issue_request(session, user, claim.id, RequestCreate(revision=1, recipient_phone="+2348012345678"), uuid4())
    row, _ = await history.lookup_request(session, invite.token)
    op = uuid4(); payload = MessageCreate(text="I did not agree to ₦5000", language="en")
    message = await history_messages.send(session, row, "worker", user.id, payload, op)
    assert (await history_messages.send(session, row, "worker", user.id, payload, op)).id == message.id
    with pytest.raises(FeatureError):
        await history_messages.send(session, row, "worker", user.id, MessageCreate(text="Changed", language="en"), op)
    async def fail(self, *args):
        raise FeatureError(503, "MODEL_UNAVAILABLE", "Fixture failure")
    monkeypatch.setattr(HistoryModelGateway, "translate", fail)
    translated = await history_messages.translate_message(session, row.id, message.id, "ha")
    assert translated.status == "failed" and translated.text is None
    page = await history_messages.messages(session, row.id, 1, 1)
    assert page.total == 1 and page.items[0].text == payload.text
    assert page.items[0].translations[0].status == "failed"
    with pytest.raises(FeatureError) as error:
        await history_messages.translate_message(session, uuid4(), message.id, "ha")
    assert error.value.code == "MESSAGE_NOT_FOUND"
    assert await session.scalar(select(func.count()).select_from(NormalizedOutcome)) == 0


async def test_changed_customer_mapping_invalidates_current_evidence(session, worker):
    user = await session.get(User, worker.user_id)
    client = User(email="customer-history@test.example", display_name="Customer")
    other = User(email="other-history@test.example", display_name="Other")
    org = Organization(name="Direct", organization_type=OrganizationType.PLATFORM)
    session.add_all([client, other, org]); await session.flush()
    job = Job(worker_id=worker.id, client_id=client.id, organization_id=org.id, title="Plumbing", agreed_amount=5000, job_type=JobType.INDEPENDENT, status=JobStatus.COMPLETED)
    session.add(job); await session.flush()
    claim = await history.create_claim(session, user, ClaimCreate(job_id=job.id, details=ClaimDetails(work_type="Plumbing", description="Notes")), uuid4())
    invite = await history.issue_request(session, user, claim.id, RequestCreate(revision=1), uuid4())
    await history.submit_response(session, invite.token, client, None, CustomerDecision(decision="confirmed", declares_customer=True, consent=True), uuid4(), "test", "test")
    assert (await history.history_counts(session, worker.id)).matched_customer_jobs == 1
    job.client_id = other.id; await session.flush()
    row, stored = await history.lookup_request(session, invite.token)
    for actor in (client, other):
        with pytest.raises(FeatureError):
            await history.authorize(session, row, stored, actor, None)
    assert (await history.history_counts(session, worker.id)).matched_customer_jobs == 0
    assert (await history.claim_view(session, stored)).response is None
    assert (await UnavailableCustomerEvidence().corroborate(job.id, other.id)).status == "not_available"


async def test_stale_audio_lease_cannot_overwrite_new_attempt(session, worker, processing_config, monkeypatch):
    user = await session.get(User, worker.user_id)
    draft = await history_drafts.enqueue(session, user, b"audio", "en", None, uuid4())
    await session.commit()
    factory = async_sessionmaker(session.bind, expire_on_commit=False)
    async def normalize(path):
        return path.with_suffix(".fixture")
    async def transcribe(self, audio, language):
        return "stale transcript", {"asr":"fixture"}
    async def extract(self, transcript, language):
        async with factory() as independent:
            row = await independent.get(HistoryDraft, draft.id)
            row.attempts += 1
            row.lease_until = now()+timedelta(minutes=5)
            await independent.commit()
        return ClaimDetails(work_type="Cleaner", description="Stale result")
    monkeypatch.setattr(history_drafts, "normalize_audio", normalize)
    monkeypatch.setattr(HistoryModelGateway, "transcribe", transcribe)
    monkeypatch.setattr(HistoryModelGateway, "extract", extract)
    assert await history_drafts.process_one(factory)
    row = await session.get(HistoryDraft, draft.id, populate_existing=True)
    assert row.status == "processing" and row.attempts == 2 and row.transcript is None
    assert list(processing_config.glob("*.upload")), "Stale worker must leave newer attempt's audio intact"
