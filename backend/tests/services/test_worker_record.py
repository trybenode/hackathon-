"""Purpose: Verify the worker's portable record is built from stored history.

Dependencies: pytest, SQLAlchemy async sessions, and app.services.worker_record.
Used by: the backend test suite and CI.
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.domain import (
    AgreementStatus,
    GuarantorAgreement,
    IdentityVerification,
    NormalizedOutcome,
    OutcomeSource,
    OutcomeStatus,
    RawOutcome,
    User,
    Worker,
)
from app.services import worker_record as service
from tests.conftest import give_guarantor

NOW = datetime.now(UTC)


async def add_outcome(
    session: AsyncSession,
    worker: Worker,
    source: OutcomeSource,
    *,
    days_ago: int,
    status: OutcomeStatus = OutcomeStatus.COMPLETED,
    client_id: str | None = None,
    confirmed: bool = True,
    import_method: str = "native",
    cancelled_by: str | None = None,
    dispute_resolution: str | None = None,
) -> None:
    key = f"job-{uuid4().hex[:8]}"
    raw = RawOutcome(
        source_id=source.id,
        external_outcome_id=key,
        payload={"status": status.value},
        payload_checksum=uuid4().hex * 2,
    )
    session.add(raw)
    await session.flush()
    session.add(
        NormalizedOutcome(
            worker_id=worker.id,
            raw_outcome_id=raw.id,
            outcome_key=key,
            status=status,
            occurred_at=NOW - timedelta(days=days_ago),
            amount=Decimal("15000.00"),
            completion_confirmed=confirmed,
            normalization_version="1",
            cancelled_by=cancelled_by,
            dispute_resolution=dispute_resolution,
            client_id=client_id,
            source_platform="other-platform" if import_method == "api" else "native",
            import_method=import_method,
            verified=True,
            quality_flags=[],
        )
    )
    await session.flush()


@pytest.fixture
async def source(session: AsyncSession) -> OutcomeSource:
    record = OutcomeSource(name=f"record-test-{uuid4()}", normalization_version="1")
    session.add(record)
    await session.flush()
    return record


async def test_record_counts_and_history(
    session: AsyncSession, worker: Worker, source: OutcomeSource
) -> None:
    user = await session.get(User, worker.user_id)
    await add_outcome(session, worker, source, days_ago=1, client_id="c1")
    await add_outcome(session, worker, source, days_ago=5, client_id="c1", confirmed=False)
    await add_outcome(session, worker, source, days_ago=9, client_id="c2")
    # The client cancelled: not the worker's fault, so not in the rate.
    await add_outcome(
        session, worker, source, days_ago=12,
        status=OutcomeStatus.CANCELLED, cancelled_by="client",
    )
    await add_outcome(
        session, worker, source, days_ago=15, client_id="c3", dispute_resolution="upheld"
    )
    await add_outcome(session, worker, source, days_ago=20, import_method="api")

    record = await service.load_record(session, user)

    assert record.verified_outcomes == 6
    assert record.completed_jobs == 5
    assert record.completion_rate == 1.0
    # c1 hired twice.
    assert record.repeat_hires == 1
    assert record.disputes == 1
    # Completed records without attributable native confirmations stay recorded work.
    assert len(record.outcomes) == 5
    assert record.outcomes[0].occurred_at > record.outcomes[1].occurred_at
    assert record.outcomes[1].status == "Recorded work"
    assert record.outcomes[0].status == "Recorded work"
    assert record.imported_record is not None
    assert record.imported_record.verified_outcomes == 1
    # Six verified outcomes is enough history to be scored.
    assert record.status == "Scored"
    assert record.score is not None and 0 <= record.score <= 1


async def test_credentials_come_from_checks_and_guarantees(
    session: AsyncSession, worker: Worker
) -> None:
    user = await session.get(User, worker.user_id)
    guarantor = User(email="john@example.com", display_name="John Parker")
    session.add_all(
        [
            guarantor,
            IdentityVerification(
                user_id=user.id,
                provider="stub",
                provider_reference="REF",
                status="verified",
                check_type="identity",
            ),
        ]
    )
    await session.flush()
    session.add(
        GuarantorAgreement(
            worker_id=worker.id,
            guarantor_user_id=guarantor.id,
            scope="Cleaning",
            conditions="No-show",
            relationship_type="employer",
            status=AgreementStatus.EXPIRED,
            verified_at=NOW - timedelta(days=400),
            valid_until=NOW - timedelta(days=35),
        )
    )
    await session.flush()

    record = await service.load_record(session, user)

    assert record.identity is not None and not record.identity.nin_verified
    assert record.identity.status == "sandbox"
    assert not record.identity_verified
    assert record.guarantor is not None
    assert record.guarantor.name == "John Parker"
    assert record.guarantor.status == "Expired"
    assert record.guarantor.relationship == "employer"
    assert record.imported_record is None


async def test_a_user_without_a_worker_profile(session: AsyncSession) -> None:
    user = User(email="nobody@example.com", display_name="Nobody")
    session.add(user)
    await session.flush()

    with pytest.raises(service.NotAWorkerError):
        await service.load_record(session, user)


async def test_released_job_shows_its_rating_on_the_record(session: AsyncSession, worker: Worker) -> None:
    from datetime import timedelta as _td

    from app.services import escrow

    user = await session.get(User, worker.user_id)
    await give_guarantor(session, worker)
    job = await escrow.create_job_link(
        session, user, title="Home cleaning", address="Lekki, Lagos",
        scheduled_at=NOW + _td(days=1), price=Decimal("25000.00"),
    )
    pending = await escrow.start_payment(
        session, job.link_token, name="Peter James", email="peter@example.com", phone="08012345678"
    )
    await escrow.handle_webhook(
        session,
        {"transactionId": "g", "transactionNumber": pending.provider_reference, "paymentStatus": "Paid"},
        delivery_id="d-record",
    )
    await escrow.mark_complete(session, user, job.id)
    await escrow.release_by_customer(session, job.link_token, code="5Z093S", rating=5)

    record = await service.load_record(session, user)
    outcome = record.outcomes[0]

    assert outcome.title == "Home cleaning"
    assert outcome.location == "Lekki, Lagos"
    assert outcome.client_name == "Peter James"
    assert outcome.rating == 5.0
    assert outcome.dispute == "none"


async def test_latest_failed_identity_supersedes_pass(session, worker):
    user = await session.get(User, worker.user_id)
    session.add_all([
        IdentityVerification(user_id=user.id, provider="real", provider_reference="old", status="verified", check_type="identity", created_at=NOW-timedelta(days=1)),
        IdentityVerification(user_id=user.id, provider="real", provider_reference="new", status="failed", check_type="identity", created_at=NOW),
    ])
    await session.flush()
    record = await service.load_record(session, user)
    assert record.identity_status == "not_verified"
    assert not record.identity_verified


@pytest.mark.parametrize("status, expires, expected", [
    (AgreementStatus.SUSPENDED, 7, "Suspended"),
    (AgreementStatus.REVOKED, 7, "Revoked"),
    (AgreementStatus.TRIGGERED, 7, "Triggered"),
    (AgreementStatus.DISPUTED, 7, "Disputed"),
    (AgreementStatus.ACTIVE, -1, "Expired"),
])
async def test_guarantor_preserves_lifecycle(session, worker, status, expires, expected):
    person = User(email="support@example.com", display_name="Support")
    session.add(person)
    await session.flush()
    session.add(GuarantorAgreement(worker_id=worker.id, guarantor_user_id=person.id, scope="Work", conditions="No show", relationship_type="employer", status=status, verified_at=NOW-timedelta(days=30), valid_until=NOW+timedelta(days=expires)))
    await session.flush()
    record = await service.load_record(session, await session.get(User, worker.user_id))
    assert record.guarantor.status == expected
    assert not record.guarantor.verified


async def test_completed_preview_is_bounded(session, worker, source):
    for index in range(23):
        await add_outcome(session, worker, source, days_ago=index)
    record = await service.load_record(session, await session.get(User, worker.user_id))
    assert record.completed_jobs == 23
    assert len(record.outcomes) == 20
    assert record.disputes is None
    assert record.repeat_hires is None
    assert record.band == "Building History"


async def test_active_guarantor_requires_both_checks_for_public_support(session, worker):
    from app.services.portability import summary_from_record
    person = User(email="sandbox-guarantor@example.com", display_name="Support")
    session.add(person); await session.flush()
    session.add_all([
        GuarantorAgreement(worker_id=worker.id, guarantor_user_id=person.id, scope="Work", conditions="No show", relationship_type="employer", status=AgreementStatus.ACTIVE, verified_at=NOW-timedelta(days=1), valid_until=NOW+timedelta(days=7)),
        IdentityVerification(user_id=person.id, provider="stub", provider_reference="identity", status="verified", check_type="identity"),
    ])
    await session.flush()
    user = await session.get(User, worker.user_id)
    record = await service.load_record(session, user)
    assert not summary_from_record(record).active_guarantor
    session.add(IdentityVerification(user_id=person.id, provider="stub", provider_reference="liveness", status="verified", check_type="liveness"))
    await session.flush()
    summary = summary_from_record(await service.load_record(session, user))
    assert summary.active_guarantor and summary.guarantor_sandbox
