"""Purpose: Verify a job's money moves through escrow as the SRS describes.

Dependencies: pytest, SQLAlchemy async sessions, and app.services.escrow.
Used by: the backend test suite and CI. Uses the stub provider throughout.
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.domain import DisputeStatus, EscrowStatus, JobStatus, User, Worker
from app.services import escrow as service
from app.services.escrow_provider import StubEscrowProvider

NOW = datetime(2026, 10, 8, 12, 0, tzinfo=UTC)


def job_request(worker: Worker) -> service.JobRequest:
    return service.JobRequest(
        worker_id=worker.id,
        title="Home cleaning",
        amount=Decimal("25000.00"),
        client_name="Peter James",
        client_email="peter@example.com",
        client_phone="08012345678",
        location="Lekki, Lagos",
        details=[{"label": "Bedrooms", "value": "2"}],
    )


def paid(escrow, *, code: str | None = "ABC123DEF4") -> dict:
    return {
        "transactionId": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
        "transactionNumber": escrow.provider_reference,
        "paymentStatus": "Paid",
        "escrowStatus": "InEscrow",
        "escrowCode": code if code is not None else "Restricted: contact PayScrow to enable",
        "amountPaid": str(escrow.total_payable),
        "currency": "NGN",
        "status": "InProgress",
    }


async def funded_job(session: AsyncSession, worker: Worker, *, code: str | None = "ABC123DEF4"):
    job, escrow = await service.open_job(session, job_request(worker))
    await service.handle_webhook(session, paid(escrow, code=code), delivery_id="d-paid")
    return job, escrow


async def test_open_job_starts_an_escrow_awaiting_payment(
    session: AsyncSession, worker: Worker
) -> None:
    job, escrow = await service.open_job(session, job_request(worker))

    assert job.status is JobStatus.ACCEPTED
    assert escrow.status is EscrowStatus.PENDING
    assert escrow.provider_reference.startswith("STUB-")
    assert escrow.payment_link
    assert service.job_stage(job, escrow) == "awaiting_payment"


async def test_paid_webhook_holds_the_money_once(session: AsyncSession, worker: Worker) -> None:
    job, escrow = await funded_job(session, worker)

    assert escrow.status is EscrowStatus.HELD
    assert escrow.escrow_code == "ABC123DEF4"
    assert escrow.provider_transaction_id
    assert job.status is JobStatus.IN_PROGRESS
    # Payscrow retries with the same delivery id; the second is a no-op.
    again = await service.handle_webhook(session, paid(escrow), delivery_id="d-paid")
    assert again == "duplicate"


async def test_restricted_code_notice_is_not_mistaken_for_a_code(
    session: AsyncSession, worker: Worker
) -> None:
    _, escrow = await funded_job(session, worker, code=None)

    assert escrow.status is EscrowStatus.HELD
    assert escrow.escrow_code is None


async def test_complete_then_client_confirms_releases(
    session: AsyncSession, worker: Worker, never_move_real_money: StubEscrowProvider
) -> None:
    user = await session.get(User, worker.user_id)
    job, escrow = await funded_job(session, worker)

    await service.mark_complete(session, user, job.id, now=NOW)
    assert job.status is JobStatus.SUBMITTED
    assert job.auto_release_at == NOW + timedelta(hours=72)
    assert service.job_stage(job, escrow) == "awaiting_confirmation"

    await service.release(session, job.id, by="client", now=NOW)

    assert never_move_real_money.applied == [(escrow.provider_transaction_id, "ABC123DEF4")]
    assert escrow.status is EscrowStatus.RELEASED
    assert job.status is JobStatus.RELEASED
    assert service.job_stage(job, escrow) == "released"


async def test_client_confirms_with_their_code(
    session: AsyncSession, worker: Worker, never_move_real_money: StubEscrowProvider
) -> None:
    """Payscrow's default: the code goes to the paying client, not into the webhook."""

    user = await session.get(User, worker.user_id)
    job, escrow = await funded_job(session, worker, code=None)
    await service.mark_complete(session, user, job.id)

    with pytest.raises(service.EscrowCodeMissingError):
        await service.release(session, job.id, by="client")
    with pytest.raises(service.EscrowStateError):
        await service.release(session, job.id, by="client", code="not a code!")

    await service.release(session, job.id, by="client", code="XYZ789ABC1")

    assert never_move_real_money.applied == [(escrow.provider_transaction_id, "XYZ789ABC1")]
    assert escrow.status is EscrowStatus.RELEASED
    # The client's code is used, never kept.
    assert escrow.escrow_code is None


async def test_paid_amount_must_match_the_order(session: AsyncSession, worker: Worker) -> None:
    job, escrow = await service.open_job(session, job_request(worker))
    payload = paid(escrow) | {"amountPaid": "100.00"}

    outcome = await service.handle_webhook(session, payload, delivery_id="d-short")

    assert outcome == "amount mismatch"
    assert escrow.status is EscrowStatus.PENDING
    assert job.status is JobStatus.ACCEPTED


async def test_complete_needs_the_money_held(session: AsyncSession, worker: Worker) -> None:
    user = await session.get(User, worker.user_id)
    job, _ = await service.open_job(session, job_request(worker))

    with pytest.raises(service.EscrowStateError):
        await service.mark_complete(session, user, job.id)


async def test_someone_elses_job_is_not_found(session: AsyncSession, worker: Worker) -> None:
    stranger = User(email="stranger@example.com", display_name="Stranger")
    session.add(stranger)
    await session.flush()
    job, _ = await funded_job(session, worker)

    with pytest.raises(service.JobNotFoundError):
        await service.mark_complete(session, stranger, job.id)


async def test_dispute_raised_then_ruled_a_refund(
    session: AsyncSession, worker: Worker, never_move_real_money: StubEscrowProvider
) -> None:
    user = await session.get(User, worker.user_id)
    job, escrow = await funded_job(session, worker)

    dispute = await service.report_issue(
        session, user, job.id, reason="Client didn't provide required access", complaint="Gate locked"
    )
    assert never_move_real_money.disputes[0][1] == "merchant"
    assert escrow.in_dispute and job.status is JobStatus.DISPUTED
    assert service.job_stage(job, escrow) == "disputed"
    with pytest.raises(service.EscrowStateError):
        await service.release(session, job.id, by="client")

    await service.handle_webhook(
        session,
        {
            "event": "dispute.status_changed",
            "eventId": "e-1",
            "transactionNumber": escrow.provider_reference,
            "disputeStage": "Resolved",
            "resolutionType": "Refund",
            "inDispute": False,
        },
        delivery_id="e-1",
    )

    assert escrow.status is EscrowStatus.REFUNDED
    assert job.status is JobStatus.CANCELLED
    assert dispute.status is DisputeStatus.RESOLVED


async def test_dispute_closed_in_the_workers_favour_releases(
    session: AsyncSession, worker: Worker
) -> None:
    user = await session.get(User, worker.user_id)
    job, escrow = await funded_job(session, worker)
    await service.report_issue(session, user, job.id, reason="Payment-related issue", complaint="")

    await service.handle_webhook(
        session,
        {
            "event": "dispute.status_changed",
            "eventId": "e-2",
            "transactionNumber": escrow.provider_reference,
            "disputeStage": "Resolved",
            "resolutionType": "Close",
        },
        delivery_id="e-2",
    )

    assert escrow.status is EscrowStatus.RELEASED
    assert job.status is JobStatus.RELEASED


async def test_auto_release_after_the_window(session: AsyncSession, worker: Worker) -> None:
    user = await session.get(User, worker.user_id)
    job, escrow = await funded_job(session, worker)
    await service.mark_complete(session, user, job.id, now=NOW)

    assert await service.release_due(session, now=NOW + timedelta(hours=71)) == []
    released = await service.release_due(session, now=NOW + timedelta(hours=73))

    assert released == [job.id]
    assert escrow.status is EscrowStatus.RELEASED


async def test_auto_release_skips_jobs_without_a_code(session: AsyncSession, worker: Worker) -> None:
    user = await session.get(User, worker.user_id)
    job, escrow = await funded_job(session, worker, code=None)
    await service.mark_complete(session, user, job.id, now=NOW)

    assert await service.release_due(session, now=NOW + timedelta(hours=73)) == []
    assert escrow.status is EscrowStatus.HELD
