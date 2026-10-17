"""Ownership/scoring separation, reviewer isolation and live limited-access gates."""

from datetime import timedelta
from decimal import Decimal
from uuid import uuid4
import pytest
from sqlalchemy import func, select
from app.core.config import get_settings
from app.models.admission import (
    OnboardingCase,
    ReviewMembership,
    OwnershipImport,
    ProvisionalRecord,
)
from app.models.domain import (
    IdentityVerification,
    Job,
    JobStatus,
    JobType,
    NormalizedOutcome,
    Organization,
    OrganizationType,
    User,
)
from app.models.portability import PlatformGrant, WorkerLink
from app.schemas.admission import (
    CaseCreate,
    DecisionInput,
    PolicySettings,
    PolicyUpdate,
)
from app.services import admission, ownership_imports
from app.services.feature_common import FeatureError, now
from app.services.review_access import consent

PDF = b"%PDF-1.4\nfixture supporting document\n%%EOF"


@pytest.fixture
async def review_setup(session, worker, monkeypatch, tmp_path):
    cfg = get_settings()
    monkeypatch.setattr(cfg, "environment", "development")
    monkeypatch.setattr(cfg, "unsigned_imports_enabled", True)
    monkeypatch.setattr(cfg, "additional_verification_enabled", True)
    monkeypatch.setattr(cfg, "s3_bucket", "")
    monkeypatch.setattr(cfg, "ownership_storage_dir", str(tmp_path))
    owner = await session.get(User, worker.user_id)
    ops = User(email="ops@example.com", display_name="Operations")
    outsider = User(email="outsider@example.com", display_name="Other")
    session.add_all([ops, outsider])
    await session.flush()
    session.add(
        ReviewMembership(user_id=ops.id, scope="operations", environment="production")
    )
    await session.flush()
    return owner, ops, outsider


async def genuine(session, worker, kind="identity", provider="test-provider"):
    row = IdentityVerification(
        user_id=worker.user_id,
        provider=provider,
        provider_reference=str(uuid4()),
        status="verified",
        check_type=kind,
        created_at=now(),
    )
    session.add(row)
    await session.flush()
    return row


def csv(worker, status="completed", identifier=None):
    return f"worker_id,job_id,date,status,cancelled_by\n{identifier or worker.id},job-1,2025-01-01,{status},\n".encode()


async def submitted(session, worker, owner, data=None):
    batch = await ownership_imports.prepare(
        session, owner, data or csv(worker), "Prior customer records", uuid4()
    )
    batch = await ownership_imports.attach(session, owner, batch.id, PDF)
    return await ownership_imports.submit(session, owner, batch.id, batch.version)


async def test_unsigned_requires_ownership_and_never_changes_verified_history(
    session, worker, review_setup
):
    owner, ops, _ = review_setup
    await genuine(session, worker)
    batch = await submitted(session, worker, owner)
    assert (await ownership_imports.provisional(session, worker.id)).rating is None
    result = await ownership_imports.decide(
        session,
        ops,
        batch.id,
        DecisionInput(
            version=batch.version,
            decision="approve",
            reason="Matched against genuine identity and supporting job references.",
            ownership_basis="Verified profile and document association checked by operations.",
        ),
    )
    assert result.state == "approved"
    score = await ownership_imports.provisional(session, worker.id)
    assert score.rating == 0.65 and score.count == 1 and score.verified is False
    assert (
        await session.scalar(select(func.count()).select_from(NormalizedOutcome)) == 0
    )
    await ownership_imports.withdraw(session, owner, batch.id, result.version)
    assert (await ownership_imports.provisional(session, worker.id)).rating is None


async def test_wrong_worker_and_signed_json_cannot_enter_unsigned_route(
    session, worker, review_setup
):
    owner, _, _ = review_setup
    for data, code in [
        (csv(worker, identifier=uuid4()), "WORKER_MISMATCH"),
        (b'{"credential_token":"tampered"}', "SIGNED_ROUTE_REQUIRED"),
        (csv(worker, status="cancelled"), "CSV_INVALID"),
    ]:
        with pytest.raises(FeatureError) as e:
            await ownership_imports.prepare(session, owner, data, "Source", uuid4())
        assert e.value.code == code


async def test_idempotency_document_immutability_and_duplicate_rows(
    session, worker, review_setup
):
    owner, _, _ = review_setup
    operation = uuid4()
    a = await ownership_imports.prepare(
        session, owner, csv(worker), "Source", operation
    )
    assert (
        await ownership_imports.prepare(
            session, owner, csv(worker), "Source", operation
        )
    ).id == a.id
    with pytest.raises(FeatureError):
        await ownership_imports.prepare(
            session, owner, csv(worker).replace(b"job-1", b"job-2"), "Source", operation
        )
    a = await ownership_imports.attach(session, owner, a.id, PDF)
    assert (
        await ownership_imports.attach(session, owner, a.id, PDF)
    ).version == a.version
    with pytest.raises(FeatureError):
        await ownership_imports.attach(session, owner, a.id, PDF + b"changed")
    with pytest.raises(FeatureError):
        await ownership_imports.prepare(
            session,
            owner,
            csv(worker) + csv(worker).split(b"\n")[1] + b"\n",
            "Source",
            uuid4(),
        )


async def test_operations_role_genuine_identity_and_basis_are_all_required(
    session, worker, review_setup
):
    owner, ops, outsider = review_setup
    batch = await submitted(session, worker, owner)
    payload = DecisionInput(
        version=batch.version,
        decision="approve",
        reason="Reviewing ownership association.",
        ownership_basis="Document compared with verified identity details.",
    )
    with pytest.raises(FeatureError) as e:
        await ownership_imports.decide(session, outsider, batch.id, payload)
    assert e.value.status == 403
    await genuine(session, worker, provider="stub")
    with pytest.raises(FeatureError) as e:
        await ownership_imports.decide(session, ops, batch.id, payload)
    assert e.value.code == "OWNERSHIP_UNRESOLVED"
    session.add(
        ReviewMembership(user_id=owner.id, scope="operations", environment="production")
    )
    await session.flush()
    with pytest.raises(FeatureError) as e:
        await ownership_imports.decide(session, owner, batch.id, payload)
    assert e.value.code == "SELF_REVIEW"


async def test_checks_then_review_then_expiring_limited_access(
    session, worker, review_setup
):
    owner, ops, _ = review_setup
    assert (
        await admission.evaluate(session, worker.id)
    ).action == "additional_verification"
    await genuine(session, worker)
    await genuine(session, worker, "liveness")
    pending = await admission.submit_case(session, owner, CaseCreate())
    assert pending.action == "manual_review"
    limited = await admission.decide(
        session,
        ops,
        pending.case_id,
        DecisionInput(
            version=pending.case_version,
            decision="approve_limited",
            reason="Verified identity and liveness; limited pilot access approved.",
        ),
    )
    assert limited.action == "limited" and limited.restrictions.max_job_value == 25000
    assert limited.expires_at <= now() + timedelta(days=30)
    assert (
        await admission.assessment_for(
            session, worker.id, "first_party", "production", "generic"
        )
    ).band == "Building History"
    await admission.enforce_job(session, worker.id, Decimal("25000"))
    with pytest.raises(FeatureError) as e:
        await admission.enforce_job(session, worker.id, Decimal("25000.01"))
    assert e.value.code == "JOB_VALUE_LIMIT"
    case = await session.get(OnboardingCase, pending.case_id)
    case.expires_at = now() - timedelta(seconds=1)
    assert (await admission.evaluate(session, worker.id)).action == "manual_review"


async def test_stale_case_self_review_and_policy_changes(session, worker, review_setup):
    owner, ops, _ = review_setup
    await genuine(session, worker)
    await genuine(session, worker, "liveness")
    pending = await admission.submit_case(session, owner, CaseCreate())
    payload = DecisionInput(
        version=pending.case_version,
        decision="approve_limited",
        reason="Reviewed all required worker evidence.",
    )
    session.add(
        ReviewMembership(user_id=owner.id, scope="operations", environment="production")
    )
    await session.flush()
    with pytest.raises(FeatureError) as e:
        await admission.decide(session, owner, pending.case_id, payload)
    assert e.value.code == "SELF_REVIEW"
    await genuine(session, worker, "liveness")
    with pytest.raises(FeatureError) as e:
        await admission.decide(session, ops, pending.case_id, payload)
    assert e.value.code == "STALE_EVIDENCE"


async def test_active_job_limit_and_funded_job_is_not_modified(
    session, worker, review_setup
):
    owner, ops, _ = review_setup
    await genuine(session, worker)
    await genuine(session, worker, "liveness")
    pending = await admission.submit_case(session, owner, CaseCreate())
    await admission.decide(
        session,
        ops,
        pending.case_id,
        DecisionInput(
            version=pending.case_version,
            decision="approve_limited",
            reason="Limited access approved after review.",
        ),
    )
    org = Organization(name="Our app", organization_type=OrganizationType.PLATFORM)
    session.add(org)
    await session.flush()
    job = Job(
        worker_id=worker.id,
        organization_id=org.id,
        job_type=JobType.INDEPENDENT,
        status=JobStatus.IN_PROGRESS,
        title="Existing funded work",
        agreed_amount=Decimal("10000"),
    )
    session.add(job)
    await session.flush()
    with pytest.raises(FeatureError) as e:
        await admission.enforce_job(session, worker.id, Decimal("100"))
    assert e.value.code == "ACTIVE_JOB_LIMIT"
    assert job.status == JobStatus.IN_PROGRESS


async def test_tenant_opt_in_and_consent_revocation(session, worker, review_setup):
    owner, _, outsider = review_setup
    org = Organization(name="Platform A", organization_type=OrganizationType.PLATFORM)
    other = Organization(name="Platform B", organization_type=OrganizationType.PLATFORM)
    session.add_all([org, other])
    await session.flush()
    session.add(
        ReviewMembership(
            user_id=outsider.id, scope=str(org.id), environment="production"
        )
    )
    grant = PlatformGrant(
        worker_id=worker.id,
        organization_id=org.id,
        token_hash="a" * 64,
        permissions=["read_history"],
        expires_at=now() + timedelta(days=7),
    )
    session.add(grant)
    await session.flush()
    session.add(
        WorkerLink(
            worker_id=worker.id,
            organization_id=org.id,
            external_worker_id="worker1",
            grant_id=grant.id,
        )
    )
    await session.flush()
    assert await admission.evaluate(session, worker.id, str(org.id)) is None
    await admission.save_policy(
        session,
        outsider,
        str(org.id),
        "production",
        "generic",
        PolicyUpdate(version=1, settings=PolicySettings(enabled=True)),
    )
    await genuine(session, worker)
    await genuine(session, worker, "liveness")
    case = await admission.submit_case(
        session, owner, CaseCreate(organization_id=org.id)
    )
    with pytest.raises(FeatureError):
        await admission.queue(session, outsider, str(other.id), "production", 1, 20)
    grant.revoked_at = now()
    await session.flush()
    with pytest.raises(FeatureError) as e:
        await admission.decide(
            session,
            outsider,
            case.case_id,
            DecisionInput(
                version=case.case_version,
                decision="approve",
                reason="Approved under our platform policy.",
            ),
        )
    assert e.value.code == "CONSENT_REQUIRED"


async def test_request_information_records_worker_reply(session, worker, review_setup):
    owner, ops, _ = review_setup
    await genuine(session, worker)
    await genuine(session, worker, "liveness")
    case = await admission.submit_case(session, owner, CaseCreate())
    result = await admission.decide(
        session,
        ops,
        case.case_id,
        DecisionInput(
            version=case.case_version,
            decision="request_information",
            reason="Please explain your earlier work experience.",
        ),
    )
    assert result.requirements == ["supporting_information"]
    with pytest.raises(FeatureError) as error:
        await admission.submit_case(session, owner, CaseCreate())
    assert error.value.code == "RESPONSE_REQUIRED"
    reply = "My earlier work was independent and has no signed credential."
    result = await admission.submit_case(session, owner, CaseCreate(response=reply))
    queued = await admission.queue(session, ops, "first_party", "production", 1, 20)
    assert queued["items"][0]["worker_response"] == reply
    assert queued["items"][0]["assessment"]["band"] == "Building History"
    assert queued["items"][0]["verification"]["liveness"] == "verified"
    assert result.action == "manual_review"


async def test_expired_unreviewed_and_orphan_documents_are_removed(
    session, worker, review_setup, tmp_path
):
    import os
    from app.services import review_storage

    owner, _, _ = review_setup
    batch = await submitted(session, worker, owner)
    row = await session.get(OwnershipImport, batch.id)
    key = row.document_key
    row.expires_at = now() - timedelta(seconds=1)
    await session.flush()
    await ownership_imports.expire(session)
    assert row.state == "expired" and row.document_key is None
    assert not (tmp_path / key.split("/")[1]).exists()
    orphan = await review_storage.store(PDF, "application/pdf")
    path = tmp_path / orphan.split("/")[1]
    old = (now() - timedelta(days=31)).timestamp()
    os.utime(path, (old, old))
    assert await ownership_imports.expire_orphans(session) == 1
    assert not path.exists()


async def test_corrected_revision_replaces_provisional_and_unknown_stays_unknown(
    session, worker, review_setup
):
    owner, ops, _ = review_setup
    await genuine(session, worker)
    first = await submitted(session, worker, owner)
    first = await ownership_imports.decide(
        session,
        ops,
        first.id,
        DecisionInput(
            version=first.version,
            decision="approve",
            reason="Checked identity and job reference association.",
            ownership_basis="Genuine identity matches independently compared contact references.",
        ),
    )
    correction = await ownership_imports.prepare(
        session,
        owner,
        csv(worker, status="unknown"),
        "Prior customer records",
        uuid4(),
        first.id,
    )
    correction = await ownership_imports.attach(session, owner, correction.id, PDF)
    correction = await ownership_imports.submit(
        session, owner, correction.id, correction.version
    )
    assert (await ownership_imports.provisional(session, worker.id)).rating is None
    await ownership_imports.decide(
        session,
        ops,
        correction.id,
        DecisionInput(
            version=correction.version,
            decision="approve",
            reason="Corrected evidence ownership reviewed.",
            ownership_basis="Same document references reviewed against verified identity.",
        ),
    )
    assert (await ownership_imports.provisional(session, worker.id)).rating is None


async def test_failed_latest_checks_and_scoring_disqualification_cannot_be_overridden(
    session, worker, review_setup, monkeypatch
):
    from dataclasses import replace

    owner, ops, _ = review_setup
    await genuine(session, worker)
    await genuine(session, worker, "liveness")
    case = await admission.submit_case(session, owner, CaseCreate())
    check = await genuine(session, worker, "liveness")
    check.status = "failed"
    await session.flush()
    assert (
        await admission.evaluate(session, worker.id)
    ).action == "additional_verification"
    base = await admission.assessment_for(
        session, worker.id, "first_party", "production", "generic"
    )

    async def disqualified(*args, **kwargs):
        return replace(base, band="Low", decision=False, status="Disqualified")

    monkeypatch.setattr(admission, "assessment_for", disqualified)
    assert (await admission.evaluate(session, worker.id)).action == "declined"
    with pytest.raises(FeatureError) as error:
        await admission.submit_case(session, owner, CaseCreate())
    assert error.value.code == "SCORING_RESTRICTION"


@pytest.mark.skipif(
    not __import__("os").environ.get("TEST_DATABASE_URL", "").startswith("postgresql"),
    reason="PostgreSQL row locks required",
)
async def test_postgres_concurrent_decisions_and_job_creation(
    session, worker, review_setup
):
    import asyncio
    from sqlalchemy.ext.asyncio import async_sessionmaker
    from tests.conftest import give_guarantor
    from app.models.admission import ReviewDecision
    from app.services.escrow import create_job_link

    owner, ops, _ = review_setup
    await genuine(session, worker)
    await genuine(session, worker, "liveness")
    await give_guarantor(session, worker)
    case = await admission.submit_case(session, owner, CaseCreate())
    worker_id, owner_id, ops_id = worker.id, owner.id, ops.id
    await session.commit()
    factory = async_sessionmaker(session.bind, expire_on_commit=False)

    async def decision():
        async with factory() as other:
            actor = await other.get(User, ops_id)
            try:
                value = await admission.decide(
                    other,
                    actor,
                    case.case_id,
                    DecisionInput(
                        version=case.case_version,
                        decision="approve_limited",
                        reason="Reviewed genuine identity and liveness checks.",
                    ),
                )
                await other.commit()
                return value.action
            except FeatureError as error:
                await other.rollback()
                return error.code

    results = await asyncio.wait_for(asyncio.gather(decision(), decision()), timeout=15)
    assert sorted(results) == ["STALE_REVISION", "limited"]

    async def create():
        async with factory() as other:
            actor = await other.get(User, owner_id)
            try:
                await create_job_link(
                    other,
                    actor,
                    title="Pilot job",
                    address="Lagos",
                    scheduled_at=now() + timedelta(days=1),
                    price=Decimal("10000"),
                )
                await other.commit()
                return "created"
            except FeatureError as error:
                await other.rollback()
                return error.code

    results = await asyncio.wait_for(asyncio.gather(create(), create()), timeout=15)
    assert sorted(results) == ["ACTIVE_JOB_LIMIT", "created"]
    assert (
        await session.scalar(
            select(func.count()).select_from(Job).where(Job.worker_id == worker_id)
        )
        == 1
    )
    assert (
        await session.scalar(
            select(func.count())
            .select_from(ReviewDecision)
            .where(ReviewDecision.entity_id == case.case_id)
        )
        == 1
    )


@pytest.mark.parametrize("access_state", ["expired", "revoked"])
async def test_funded_job_can_complete_and_settle_after_access_ends(
    session, worker, review_setup, access_state
):
    from tests.conftest import give_guarantor
    from tests.services.test_escrow import paid_job, CODE
    from app.services import escrow
    from app.models.domain import EscrowStatus

    owner, ops, _ = review_setup
    await genuine(session, worker)
    await genuine(session, worker, "liveness")
    await give_guarantor(session, worker)
    pending = await admission.submit_case(session, owner, CaseCreate())
    limited = await admission.decide(
        session,
        ops,
        pending.case_id,
        DecisionInput(
            version=pending.case_version,
            decision="approve_limited",
            reason="Limited access approved with genuine verification.",
        ),
    )
    job, payment = await paid_job(session, worker)
    row = await session.get(OnboardingCase, limited.case_id)
    if access_state == "expired":
        row.expires_at = now() - timedelta(seconds=1)
    else:
        await admission.decide(
            session,
            ops,
            row.id,
            DecisionInput(
                version=row.version,
                decision="revoke",
                reason="Pilot onboarding access withdrawn by operations.",
            ),
        )
    with pytest.raises(FeatureError):
        await admission.enforce_job(session, worker.id, Decimal("100"))
    await escrow.mark_complete(session, owner, job.id)
    await escrow.release_by_customer(session, job.link_token, code=CODE, rating=5)
    assert job.status == JobStatus.RELEASED and payment.status == EscrowStatus.RELEASED


async def test_tenant_approval_and_policy_change_do_not_change_verified_assessment(
    session, worker, review_setup
):
    owner, _, tenant_reviewer = review_setup
    org = Organization(
        name="Consenting platform", organization_type=OrganizationType.PLATFORM
    )
    session.add(org)
    await session.flush()
    scope = str(org.id)
    session.add(
        ReviewMembership(
            user_id=tenant_reviewer.id, scope=scope, environment="production"
        )
    )
    grant = PlatformGrant(
        worker_id=worker.id,
        organization_id=org.id,
        token_hash="f" * 64,
        permissions=["read_history"],
        expires_at=now() + timedelta(days=7),
    )
    session.add(grant)
    await session.flush()
    session.add(
        WorkerLink(
            worker_id=worker.id,
            organization_id=org.id,
            external_worker_id="mapped-worker",
            grant_id=grant.id,
        )
    )
    await session.flush()
    first = await admission.save_policy(
        session,
        tenant_reviewer,
        scope,
        "production",
        "generic",
        PolicyUpdate(version=1, settings=PolicySettings(enabled=True)),
    )
    await genuine(session, worker)
    await genuine(session, worker, "liveness")
    before = await admission.assessment_for(
        session, worker.id, scope, "production", "generic"
    )
    pending = await admission.submit_case(
        session, owner, CaseCreate(organization_id=org.id)
    )
    approved = await admission.decide(
        session,
        tenant_reviewer,
        pending.case_id,
        DecisionInput(
            version=pending.case_version,
            decision="approve",
            reason="Approved under this platform onboarding policy.",
        ),
    )
    assert approved.action == "approved"
    after = await admission.assessment_for(
        session, worker.id, scope, "production", "generic"
    )
    assert (
        after == before and after.band == "Building History" and after.decision is False
    )
    updated = await admission.save_policy(
        session,
        tenant_reviewer,
        scope,
        "production",
        "generic",
        PolicyUpdate(
            version=first["version"],
            settings=PolicySettings(enabled=True, approval_days=14),
        ),
    )
    assert (
        await admission.evaluate(session, worker.id, scope)
    ).action == "manual_review"
    with pytest.raises(FeatureError) as failure:
        await admission.save_policy(
            session,
            tenant_reviewer,
            scope,
            "production",
            "generic",
            PolicyUpdate(
                version=first["version"], settings=PolicySettings(enabled=True)
            ),
        )
    assert failure.value.code == "STALE_POLICY"
