"""Purpose: Verify the guarantor dashboard reads only that guarantor's rows.

Dependencies: pytest, SQLAlchemy async sessions, and app.services.dashboard.
Used by: the backend test suite and CI.
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.domain import (
    AgreementStatus,
    GuarantorAgreement,
    Job,
    JobStatus,
    JobType,
    Organization,
    OrganizationType,
    User,
    Worker,
)
from app.services import dashboard as service

NOW = datetime.now(tz=UTC)


async def build_guarantee(
    session: AsyncSession,
    worker: Worker,
    guarantor: User,
    *,
    job_status: JobStatus,
    agreement_status: AgreementStatus = AgreementStatus.ACTIVE,
    valid_days: int = 60,
) -> GuarantorAgreement:
    organization = Organization(name="Sparkle", organization_type=OrganizationType.EMPLOYER)
    session.add(organization)
    await session.flush()

    job = Job(
        worker_id=worker.id,
        organization_id=organization.id,
        job_type=JobType.INDEPENDENT,
        status=job_status,
        title="Home cleaning",
        agreed_amount=Decimal("25000.00"),
    )
    session.add(job)
    await session.flush()

    agreement = GuarantorAgreement(
        worker_id=worker.id,
        guarantor_user_id=guarantor.id,
        job_id=job.id,
        scope="Cleaning",
        conditions="Covers no-show.",
        relationship_type="sibling",
        status=agreement_status,
        valid_until=NOW + timedelta(days=valid_days),
        signed_at=NOW - timedelta(days=3),
        verified_at=NOW - timedelta(days=3),
    )
    session.add(agreement)
    await session.flush()
    return agreement


async def test_summary_counts_active_and_completed(
    session: AsyncSession, worker: Worker
) -> None:
    guarantor = User(email="grace@example.com", display_name="Grace G")
    session.add(guarantor)
    await session.flush()

    await build_guarantee(session, worker, guarantor, job_status=JobStatus.IN_PROGRESS)
    await build_guarantee(session, worker, guarantor, job_status=JobStatus.COMPLETED)

    summary = await service.load_summary(session, guarantor.id)

    assert summary.active_count == 1
    # A finished job reads as Completed even while the instrument is active.
    assert summary.completed_count == 1
    assert {card.status for card in summary.guarantees} == {"Active", "Completed"}
    assert {card.bucket for card in summary.guarantees} == {"active", "completed"}
    assert summary.guarantees[0].amount == Decimal("25000.00")


async def test_triggered_stays_active_and_revoked_closes(
    session: AsyncSession, worker: Worker
) -> None:
    """A called-in guarantee is a live obligation; a revoked one is over."""

    guarantor = User(email="grace@example.com", display_name="Grace G")
    session.add(guarantor)
    await session.flush()

    triggered = await build_guarantee(
        session,
        worker,
        guarantor,
        job_status=JobStatus.IN_PROGRESS,
        agreement_status=AgreementStatus.TRIGGERED,
    )
    revoked = await build_guarantee(
        session,
        worker,
        guarantor,
        job_status=JobStatus.IN_PROGRESS,
        agreement_status=AgreementStatus.REVOKED,
    )

    summary = await service.load_summary(session, guarantor.id)
    by_id = {card.instrument_id: card for card in summary.guarantees}

    # A claim is running, so the guarantor still has something to answer.
    assert by_id[triggered.id].bucket == "active"
    assert by_id[revoked.id].bucket == "completed"
    # The card still says what actually happened.
    assert by_id[triggered.id].status == "Triggered"
    assert by_id[revoked.id].status == "Revoked"
    assert summary.active_count == 1
    assert summary.completed_count == 1


async def test_triggered_outranks_a_finished_job(
    session: AsyncSession, worker: Worker
) -> None:
    """The claim outlives the work: a finished job does not close a claim."""

    guarantor = User(email="grace@example.com", display_name="Grace G")
    session.add(guarantor)
    await session.flush()

    await build_guarantee(
        session,
        worker,
        guarantor,
        job_status=JobStatus.COMPLETED,
        agreement_status=AgreementStatus.TRIGGERED,
    )

    summary = await service.load_summary(session, guarantor.id)

    assert summary.guarantees[0].bucket == "active"
    assert summary.active_count == 1


async def test_pending_requests_are_their_own_bucket(
    session: AsyncSession, worker: Worker
) -> None:
    guarantor = User(email="grace@example.com", display_name="Grace G")
    session.add(guarantor)
    await session.flush()

    await build_guarantee(
        session,
        worker,
        guarantor,
        job_status=JobStatus.ACCEPTED,
        agreement_status=AgreementStatus.PENDING_SIGNATURE,
    )

    summary = await service.load_summary(session, guarantor.id)

    assert summary.guarantees[0].bucket == "pending"
    assert summary.active_count == 0
    assert summary.completed_count == 0


async def test_resolved_claims_move_to_completed(
    session: AsyncSession, worker: Worker
) -> None:
    """Disputed stays active; paid and dismissed are done."""

    guarantor = User(email="grace@example.com", display_name="Grace G")
    session.add(guarantor)
    await session.flush()

    disputed = await build_guarantee(
        session, worker, guarantor, job_status=JobStatus.IN_PROGRESS,
        agreement_status=AgreementStatus.DISPUTED,
    )
    paid = await build_guarantee(
        session, worker, guarantor, job_status=JobStatus.IN_PROGRESS,
        agreement_status=AgreementStatus.PAID,
    )
    dismissed = await build_guarantee(
        session, worker, guarantor, job_status=JobStatus.IN_PROGRESS,
        agreement_status=AgreementStatus.DISMISSED,
    )

    summary = await service.load_summary(session, guarantor.id)
    by_id = {card.instrument_id: card for card in summary.guarantees}

    assert by_id[disputed.id].bucket == "active"
    assert by_id[paid.id].bucket == "completed"
    assert by_id[dismissed.id].bucket == "completed"
    assert by_id[paid.id].status == "Paid"
    assert by_id[dismissed.id].status == "Dismissed"


async def test_summary_is_scoped_to_one_guarantor(
    session: AsyncSession, worker: Worker
) -> None:
    mine = User(email="mine@example.com", display_name="Mine")
    theirs = User(email="theirs@example.com", display_name="Theirs")
    session.add_all([mine, theirs])
    await session.flush()

    await build_guarantee(session, worker, theirs, job_status=JobStatus.IN_PROGRESS)

    summary = await service.load_summary(session, mine.id)

    assert summary.guarantees == []
    assert summary.active_count == 0


async def test_action_required_picks_the_waiting_request(
    session: AsyncSession, worker: Worker
) -> None:
    guarantor = User(email="grace@example.com", display_name="Grace G")
    session.add(guarantor)
    await session.flush()

    await build_guarantee(
        session,
        worker,
        guarantor,
        job_status=JobStatus.ACCEPTED,
        agreement_status=AgreementStatus.PENDING_SIGNATURE,
    )

    summary = await service.load_summary(session, guarantor.id)

    assert summary.action_required is not None
    assert summary.action_required.status == "Pending Signature"


async def test_notifications_sort_without_timezone_errors(
    session: AsyncSession, worker: Worker
) -> None:
    """Stored timestamps are naive on SQLite and aware on Postgres."""

    guarantor = User(email="grace@example.com", display_name="Grace G")
    session.add(guarantor)
    await session.flush()

    # One expiring soon and one far off, so both branches are built and sorted.
    await build_guarantee(session, worker, guarantor, job_status=JobStatus.IN_PROGRESS, valid_days=3)
    await build_guarantee(session, worker, guarantor, job_status=JobStatus.IN_PROGRESS, valid_days=300)

    items = await service.load_notifications(session, guarantor.id)

    assert any(item.icon == "calendar" for item in items)
    assert [item.at for item in items] == sorted((item.at for item in items), reverse=True)
