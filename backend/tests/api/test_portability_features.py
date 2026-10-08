"""Acceptance checks crossing identity, evidence, consent and review boundaries."""
from datetime import timedelta
from uuid import UUID, uuid4
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from app.api.v1.endpoints.auth import current_user
from app.db.session import get_db_session
from app.main import app
from app.models.domain import *
from app.models.portability import PlatformKey, Review, ShareGrant
from app.services.portability import digest, now
from app.services import reviews

@pytest_asyncio.fixture
async def api(session, worker, monkeypatch):
    actor = {"user": await session.get(User, worker.user_id)}
    actor_id = [actor["user"].id]
    async def db():
        actor_id[0] = actor["user"].id
        try:
            yield session
        except Exception:
            await session.rollback()
            # API isolation expires fixture objects on rollback; reload the actor.
            actor["user"] = await session.get(User, actor_id[0])
            raise
    async def user():
        return actor["user"]
    async def limits(*args): pass
    monkeypatch.setattr(reviews, "limit_attempts", limits)
    app.dependency_overrides[get_db_session] = db
    app.dependency_overrides[current_user] = user
    await session.commit()
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            yield client, actor
    finally:
        app.dependency_overrides.clear()

async def platform(session, name="Platform A", attest=False):
    org = Organization(name=name, organization_type=OrganizationType.PLATFORM)
    session.add(org)
    await session.flush()
    key = f"test-{uuid4()}"
    session.add(PlatformKey(organization_id=org.id, key_hash=digest(key), can_attest=attest))
    await session.commit()
    return org, {"X-API-Key": key}

async def link(client, org, headers, permissions=("read_history", "import_history")):
    grant = await client.post("/api/v1/me/worker/platform-grants", json={"organization_id": str(org.id), "permissions": list(permissions)})
    assert grant.status_code == 201, grant.text
    result = await client.post("/api/v1/platform/worker-links", headers=headers, json={"external_worker_id": "worker-1", "consent_token": grant.json()["token"]})
    assert result.status_code == 201, result.text
    return grant.json()

@pytest.mark.asyncio
async def test_two_platform_exchange_retries_and_revocation(api, session):
    client, _ = api
    org_a, a = await platform(session, attest=True)
    org_b, b = await platform(session, "Platform B")
    grant_a = await link(client, org_a, a)
    grant_b = await link(client, org_b, b, ("read_history",))
    payload = {"outcomes": [{"source_record_id": "prior-1", "occurred_at": now().isoformat(), "status": "completed", "dispute_resolution": None, "attest": True}]}
    url = "/api/v1/platform/workers/worker-1/history/import"
    first = await client.post(url, headers={**a, "Idempotency-Key": "batch-1"}, json=payload)
    assert first.status_code == 200, first.text
    assert first.json()["verified_outcomes"] == 1
    replay = await client.post(url, headers={**a, "Idempotency-Key": "batch-1"}, json=payload)
    assert replay.json() == first.json()
    duplicate = await client.post(url, headers={**a, "Idempotency-Key": "batch-2"}, json=payload)
    assert duplicate.json()["duplicate_outcomes"] == 1
    changed = {"outcomes": [{**payload["outcomes"][0], "status": "no_show"}]}
    assert (await client.post(url, headers={**a, "Idempotency-Key": "batch-1"}, json=changed)).status_code == 409
    history = await client.get("/api/v1/platform/workers/worker-1/history", headers=b)
    assert history.status_code == 200
    assert history.json()["total"] == 1
    item = history.json()["items"][0]
    assert item["source_name"] == "Platform A"
    assert item["verification_method"] == "platform_attested"
    assert item["verified_by_org_id"] == grant_a["organization_id"]
    assert "client_id" not in item
    await client.delete(f"/api/v1/me/worker/platform-grants/{grant_b['id']}")
    assert (await client.get("/api/v1/platform/workers/worker-1/history", headers=b)).status_code == 403
    assert await session.scalar(select(func.count()).select_from(NormalizedOutcome)) == 1

@pytest.mark.asyncio
async def test_claims_are_not_verification_and_tenants_are_isolated(api, session):
    client, _ = api
    org, a = await platform(session)
    _, b = await platform(session, "Other")
    grant = await link(client, org, a)
    assert (await client.post("/api/v1/platform/worker-links", headers=b, json={"external_worker_id": "worker-1", "consent_token": grant["token"]})).status_code == 403
    url = "/api/v1/platform/workers/worker-1/history/import"
    payload = {"outcomes": [{"source_record_id": "outside", "occurred_at": now().isoformat(), "status": "completed", "attest": True}]}
    assert (await client.post(url, headers={**a, "Idempotency-Key": "x"}, json=payload)).status_code == 403
    payload["outcomes"][0]["attest"] = False
    response = await client.post(url, headers={**a, "Idempotency-Key": "x"}, json=payload)
    assert response.json()["verified_outcomes"] == 0, response.text
    response = await client.get("/api/v1/me/worker/record")
    assert response.status_code == 200, response.text
    record = response.json()
    assert record["assessment"]["band"] == "Building History"
    assert record["self_declared_outcomes"] == 1
    assert record["starting_rating"] <= .65

@pytest.mark.asyncio
async def test_summary_privacy_live_status_and_expiry(api, session):
    client, actor = api
    grant = (await client.post("/api/v1/me/worker/shares")).json()
    url = f"/api/v1/verification/{grant['token']}"
    response = await client.get(url)
    assert response.status_code == 200, response.text
    assert response.json()["display_name"] == "Jane A."
    for field in ["outcomes", "worker_id", "email", "credential_token", "document_reference", "client_id"]:
        assert field not in response.json()
    assert "no-store" in response.headers["cache-control"]
    assert response.headers["referrer-policy"] == "no-referrer"
    session.add(IdentityVerification(user_id=actor["user"].id, provider="stub", provider_reference="secret-reference", status="verified", check_type="identity"))
    await session.commit()
    assert (await client.get(url)).json()["identity"]["status"] == "sandbox"
    row = await session.get(ShareGrant, UUID(grant["id"]))
    row.expires_at = now()-timedelta(seconds=1)
    await session.commit()
    assert (await client.get(url)).status_code == 410
    fresh = (await client.post("/api/v1/me/worker/shares")).json()
    assert (await client.delete(f"/api/v1/me/worker/shares/{fresh['id']}")).status_code == 204
    assert (await client.get(f"/api/v1/verification/{fresh['token']}")).status_code == 410
    listing = (await client.get("/api/v1/me/worker/shares")).json()
    assert all(row["token"] is None for row in listing["items"])

async def protected_job(session, worker):
    customer = User(email=f"{uuid4()}@example.com", display_name="Customer")
    org = Organization(name="Direct", organization_type=OrganizationType.PLATFORM)
    session.add_all([customer, org]); await session.flush()
    job = Job(worker_id=worker.id, client_id=customer.id, organization_id=org.id, job_type=JobType.INDEPENDENT, status=JobStatus.COMPLETED, title="Cleaning", agreed_amount=1000)
    session.add(job); await session.flush()
    source = OutcomeSource(name=str(uuid4()), normalization_version="native")
    session.add(source); await session.flush()
    raw = RawOutcome(source_id=source.id, external_outcome_id="job", payload={}, payload_checksum="0"*64)
    session.add(raw); await session.flush()
    outcome = NormalizedOutcome(worker_id=worker.id, job_id=job.id, raw_outcome_id=raw.id, outcome_key=str(job.id), occurred_at=now(), status=OutcomeStatus.COMPLETED, completion_confirmed=True, verified=True, normalization_version="native")
    confirmation = JobConfirmation(job_id=job.id, confirmer_id=customer.id, confirmer_role="client", confirmed=True, confirmed_at=now())
    session.add_all([outcome, confirmation,
        IdentityVerification(user_id=customer.id, provider="provider", provider_reference="ref", status="verified", check_type="identity"),
        JobConfirmation(job_id=job.id, confirmer_id=worker.user_id, confirmer_role="worker", confirmed=True, confirmed_at=now()),
        EscrowTransaction(job_id=job.id, amount=1000, micro_premium=10, provider_reference="funded", cover_active=True, status=EscrowStatus.HELD),
        InsurancePolicy(job_id=job.id, premium=10, coverage_amount=1000, provider_reference="cover", status=InsuranceStatus.ACTIVE),
        ProviderOperation(provider="vesti", operation_type="premium_payment", entity_type="job", entity_id=job.id, idempotency_key=str(job.id), status=ProviderOperationStatus.SUCCEEDED)])
    await session.commit()
    return customer, job, outcome, confirmation

@pytest.mark.asyncio
async def test_review_receipt_idempotency_and_rating(api, session, worker):
    client, actor = api
    customer, job, outcome, _ = await protected_job(session, worker)
    actor["user"] = customer
    check = await client.get(f"/api/v1/jobs/{job.id}/review-eligibility")
    assert check.json()["eligible"], check.text
    url = f"/api/v1/jobs/{job.id}/review"
    payload = {"rating": 4, "comment": "Private comment"}
    result = await client.post(url, headers={"Idempotency-Key": "r1"}, json=payload)
    assert result.status_code == 201, result.text
    assert "comment" not in result.json()
    assert (await client.post(url, headers={"Idempotency-Key": "r1"}, json=payload)).json() == result.json()
    assert (await client.post(url, headers={"Idempotency-Key": "r2"}, json=payload)).status_code == 409
    await session.refresh(outcome)
    assert float(outcome.rating) == 4
    assert await session.scalar(select(func.count()).select_from(Review)) == 1

@pytest.mark.asyncio
@pytest.mark.parametrize("blocker", ["auto_release", "dispute", "unverified", "unprotected", "platform", "refunded", "wrong_customer"])
async def test_review_restrictions(api, session, worker, blocker):
    client, actor = api
    customer, job, _, confirmation = await protected_job(session, worker)
    actor["user"] = customer
    if blocker == "auto_release":
        confirmation.confirmed = False; job.status = JobStatus.RELEASED
    elif blocker == "dispute":
        session.add(Dispute(job_id=job.id, opened_by_id=customer.id, reason="Quality", status=DisputeStatus.OPEN))
    elif blocker == "unverified":
        check = await session.scalar(select(IdentityVerification).where(IdentityVerification.user_id == customer.id)); check.status = "failed"
    elif blocker in ("unprotected", "refunded"):
        escrow = await session.scalar(select(EscrowTransaction).where(EscrowTransaction.job_id == job.id))
        if blocker == "refunded": escrow.status = EscrowStatus.REFUNDED
        else: escrow.cover_active = False
    elif blocker == "platform": job.job_type = JobType.PLATFORM
    else: actor["user"] = await session.get(User, worker.user_id)
    await session.commit()
    response = await client.post(f"/api/v1/jobs/{job.id}/review", headers={"Idempotency-Key": "x"}, json={"rating": 5})
    assert response.status_code == (404 if blocker == "wrong_customer" else 403), response.text
    assert await session.scalar(select(func.count()).select_from(Review)) == 0

def test_openapi_security():
    paths = app.openapi()["paths"]
    assert paths["/api/v1/platform/worker-links"]["post"]["security"] == [{"PlatformKey": []}]
    assert paths["/api/v1/me/worker/shares"]["post"]["security"] == [{"UserSession": []}]
    assert "security" not in paths["/api/v1/verification/{token}"]["get"]

@pytest.mark.asyncio
async def test_permission_expiry_key_revocation_and_grant_ownership(api, session, worker):
    from app.models.portability import PlatformGrant
    client, actor = api
    org, key = await platform(session)
    worker_id = worker.id
    approval = await link(client, org, key, ("import_history",))
    assert (await client.get("/api/v1/platform/workers/worker-1/history", headers=key)).status_code == 403
    assert (await client.post("/api/v1/trust/query", headers=key, json={"worker_id": str(worker_id), "platform_type": "generic", "job_context": {"job_type": "cleaning", "value_band": "low"}})).status_code == 403
    assert (await client.post("/api/v1/platform/worker-links", headers=key, json={"external_worker_id": "another-account", "consent_token": approval["token"]})).status_code == 409
    grant = await session.get(PlatformGrant, UUID(approval["id"]))
    grant.expires_at = now()-timedelta(seconds=1)
    await session.commit()
    payload = {"outcomes": [{"source_record_id": "one", "occurred_at": now().isoformat(), "status": "completed"}]}
    result = await client.post("/api/v1/platform/workers/worker-1/history/import", headers={**key, "Idempotency-Key": "new"}, json=payload)
    assert result.status_code == 403 and result.json()["code"] == "CONSENT_EXPIRED"
    share = (await client.post("/api/v1/me/worker/shares")).json()
    intruder = User(email=f"{uuid4()}@example.com", display_name="Other worker")
    session.add(intruder); await session.flush()
    session.add(Worker(user_id=intruder.id)); await session.commit()
    actor["user"] = intruder
    assert (await client.delete(f"/api/v1/me/worker/shares/{share['id']}")).status_code == 404
    assert (await client.delete(f"/api/v1/me/worker/platform-grants/{approval['id']}")).status_code == 404
    stored_key = await session.scalar(select(PlatformKey).where(PlatformKey.key_hash == digest(key["X-API-Key"])))
    stored_key.revoked_at = now(); await session.commit()
    assert (await client.get("/api/v1/platform/workers/worker-1/history", headers=key)).status_code == 401


@pytest.mark.asyncio
async def test_import_conflict_rolls_back_entire_batch(api, session):
    from app.models.portability import ImportReceipt
    client, _ = api
    org, key = await platform(session)
    await link(client, org, key)
    original = {"source_record_id": "original", "occurred_at": now().isoformat(), "status": "completed"}
    url = "/api/v1/platform/workers/worker-1/history/import"
    assert (await client.post(url, headers={**key, "Idempotency-Key": "first"}, json={"outcomes": [original]})).status_code == 200
    result = await client.post(url, headers={**key, "Idempotency-Key": "conflict"}, json={"outcomes": [{**original, "source_record_id": "must-rollback"}, {**original, "status": "no_show"}]})
    assert result.status_code == 409
    assert result.json()["code"] == "SOURCE_RECORD_CONFLICT"
    assert await session.scalar(select(func.count()).select_from(NormalizedOutcome)) == 1
    assert await session.scalar(select(func.count()).select_from(ImportReceipt)) == 1


@pytest.mark.asyncio
async def test_public_summary_is_small_and_excludes_street_address(api, session, worker):
    client, _ = api
    worker.location = "12 Secret Road, Apt 8, Lekki, Lagos"
    await session.commit()
    share = (await client.post("/api/v1/me/worker/shares")).json()
    result = await client.get(f"/api/v1/verification/{share['token']}")
    assert result.json()["location"] == "Lagos"
    assert "Secret" not in result.text
    assert len(result.content) < 20_000


@pytest.mark.asyncio
async def test_review_daily_limit_and_private_audit(api, session, worker):
    client, actor = api
    customer, job, _, _ = await protected_job(session, worker)
    actor["user"] = customer
    job_id = job.id
    identity = await session.scalar(select(IdentityVerification).where(IdentityVerification.user_id == customer.id))
    # Seed historical receipts without pretending the current job has been reviewed.
    for index in range(10):
        other = Job(worker_id=worker.id, client_id=customer.id, organization_id=job.organization_id, job_type=JobType.INDEPENDENT, title="Previous", agreed_amount=1000)
        session.add(other); await session.flush()
        session.add(Review(job_id=other.id, reviewer_id=customer.id, identity_verification_id=identity.id, rating=4, comment="secret", idempotency_key=f"prior-{index}", payload_hash="0"*64, created_at=now()-timedelta(hours=1)))
    await session.commit()
    result = await client.post(f"/api/v1/jobs/{job_id}/review", headers={"Idempotency-Key": "today"}, json={"rating": 5, "comment": "private"})
    assert result.status_code == 429 and result.json()["code"] == "REVIEW_VELOCITY_LIMIT"
    assert int(result.headers["retry-after"]) > 0
    prior = (await session.scalars(select(Review))).all()
    for receipt in prior:
        receipt.created_at = now()-timedelta(hours=25)
    await session.commit()
    result = await client.post(f"/api/v1/jobs/{job_id}/review", headers={"Idempotency-Key": "today"}, json={"rating": 5, "comment": "private"})
    assert result.status_code == 201, result.text
    events = (await session.scalars(select(AuditEvent).where(AuditEvent.entity_type == "review"))).all()
    assert len(events) == 1
    assert "private" not in str(events[0].event_metadata)


@pytest.mark.asyncio
async def test_credential_export_import_integrity_and_provenance(api, session, worker, monkeypatch):
    from app.api.v1.endpoints import credentials
    from types import SimpleNamespace
    client, _ = api
    monkeypatch.setattr(credentials, "settings", SimpleNamespace(credential_signing_secret="test-secret-"*4))
    org, key = await platform(session, attest=True)
    await link(client, org, key)
    payload = {"outcomes": [{"source_record_id": "verified", "occurred_at": now().isoformat(), "status": "completed", "rating": 4, "attest": True}]}
    assert (await client.post("/api/v1/platform/workers/worker-1/history/import", headers={**key, "Idempotency-Key": "attested"}, json=payload)).status_code == 200
    exported = await client.get(f"/api/v1/workers/{worker.id}/credentials/export")
    assert exported.status_code == 200, exported.text
    token = exported.json()["credential_token"]
    from app.services.credentials import verify_bundle
    claims = verify_bundle(token, "test-secret-"*4)
    assert claims["outcomes"][0]["verification_method"] == "platform_attested"
    assert "average_rating" in claims["outcomes"][0]["available_signals"]
    url = f"/api/v1/workers/{worker.id}/credentials/import"
    response = await client.post(url, json={"credential_token": token, "source_platform": "Source"})
    assert response.status_code == 200 and response.json()["imported_outcomes"] == 0
    assert (await client.post(url, json={"credential_token": token, "source_platform": "Source"})).json()["imported_outcomes"] == 0
    assert (await client.post(url, json={"credential_token": token[:-3]+"xxx", "source_platform": "Source"})).status_code == 422
    assert (await client.get(f"/api/v1/workers/{uuid4()}/credentials/export")).status_code == 404


@pytest.mark.asyncio
async def test_concurrent_review_submission_on_postgres(session, worker):
    import asyncio
    import os
    from sqlalchemy.ext.asyncio import async_sessionmaker
    from app.schemas.portability import ReviewRequest
    from app.services.portability import FeatureError
    if not os.getenv("TEST_DATABASE_URL"):
        pytest.skip("PostgreSQL row-lock acceptance test")
    customer, job, _, _ = await protected_job(session, worker)
    customer_id, job_id = customer.id, job.id
    factory = async_sessionmaker(session.bind, expire_on_commit=False)
    async def submit(key):
        async with factory() as db:
            user = await db.get(User, customer_id)
            try:
                result = await reviews.submit_review(db, user, job_id, ReviewRequest(rating=5), key)
                await db.commit()
                return result
            except FeatureError as error:
                await db.rollback()
                return error
    first, second = await asyncio.gather(submit("concurrent-a"), submit("concurrent-b"))
    assert sum(isinstance(item, FeatureError) for item in (first, second)) == 1
    assert next(item for item in (first, second) if isinstance(item, FeatureError)).code == "REVIEW_EXISTS"
    assert await session.scalar(select(func.count()).select_from(Review)) == 1


@pytest.mark.asyncio
async def test_explicit_absence_and_unknown_evidence_are_different_payloads(api, session):
    client, _ = api
    org, key = await platform(session, attest=True)
    await link(client, org, key)
    record = {"source_record_id": "unknown-dispute", "occurred_at": now().isoformat(), "status": "completed", "attest": True}
    url = "/api/v1/platform/workers/worker-1/history/import"
    assert (await client.post(url, headers={**key, "Idempotency-Key": "unknown"}, json={"outcomes": [record]})).status_code == 200
    known = {"outcomes": [{**record, "dispute_resolution": None}]}
    replay = await client.post(url, headers={**key, "Idempotency-Key": "unknown"}, json=known)
    assert replay.status_code == 409 and replay.json()["code"] == "IDEMPOTENCY_CONFLICT"
    changed = await client.post(url, headers={**key, "Idempotency-Key": "known"}, json=known)
    assert changed.status_code == 409 and changed.json()["code"] == "SOURCE_RECORD_CONFLICT"
    row = await session.scalar(select(NormalizedOutcome))
    assert "dispute_rate" not in row.available_signals
