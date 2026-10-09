"""Purpose: Verify a job's money moves through escrow as the SRS describes.

Dependencies: pytest, SQLAlchemy async sessions, and app.services.escrow.
Used by: the backend test suite and CI. Uses the stub provider and the logging
email sender throughout.
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.domain import DisputeStatus, EscrowStatus, JobStatus, User, Worker
from app.services import escrow as service
from app.services.email_sender import LoggingEmailSender
from app.services.escrow_provider import StubEscrowProvider

NOW = datetime(2026, 10, 8, 12, 0, tzinfo=UTC)
CLIENT_CODE = "XYZ789ABC1"


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


def paid(escrow) -> dict:
    return {
        "transactionId": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
        "transactionNumber": escrow.provider_reference,
        "paymentStatus": "Paid",
        "escrowStatus": "InEscrow",
        "amountPaid": str(escrow.total_payable),
        "currency": "NGN",
        "status": "InProgress",
    }


async def funded_job(session: AsyncSession, worker: Worker):
    job, escrow = await service.open_job(session, job_request(worker))
    await service.handle_webhook(session, paid(escrow), delivery_id="d-paid")
    return job, escrow


async def completed_job(session: AsyncSession, worker: Worker, *, at: datetime = NOW):
    user = await session.get(User, worker.user_id)
    job, escrow = await funded_job(session, worker)
    await service.mark_complete(session, user, job.id, now=at)
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


async def test_worker_needs_a_phone_for_escrow(session: AsyncSession, worker: Worker) -> None:
    user = await session.get(User, worker.user_id)
    user.phone = None
    await session.flush()

    with pytest.raises(service.EscrowStateError, match="phone number"):
        await service.open_job(session, job_request(worker))


async def test_paid_webhook_holds_the_money_once(session: AsyncSession, worker: Worker) -> None:
    job, escrow = await funded_job(session, worker)

    assert escrow.status is EscrowStatus.HELD
    assert escrow.provider_transaction_id
    assert job.status is JobStatus.IN_PROGRESS
    # Payscrow retries with the same delivery id; the second is a no-op.
    again = await service.handle_webhook(session, paid(escrow), delivery_id="d-paid")
    assert again == "duplicate"


async def test_paid_amount_must_match_the_order(session: AsyncSession, worker: Worker) -> None:
    job, escrow = await service.open_job(session, job_request(worker))
    payload = paid(escrow) | {"amountPaid": "100.00"}

    outcome = await service.handle_webhook(session, payload, delivery_id="d-short")

    assert outcome == "amount mismatch"
    assert escrow.status is EscrowStatus.PENDING
    assert job.status is JobStatus.ACCEPTED


async def test_a_code_in_the_webhook_cannot_release_anything(
    session: AsyncSession, worker: Worker
) -> None:
    """Even if Payscrow sent the code, only the client can release."""

    user = await session.get(User, worker.user_id)
    job, escrow = await service.open_job(session, job_request(worker))
    await service.handle_webhook(
        session, paid(escrow) | {"escrowCode": "ABC123DEF4"}, delivery_id="d-code"
    )
    await service.mark_complete(session, user, job.id)

    with pytest.raises(service.EscrowCodeMissingError):
        await service.release(session, job.id, by="client", code=None)
    assert escrow.status is EscrowStatus.HELD


async def test_client_confirms_with_their_code(
    session: AsyncSession, worker: Worker, never_move_real_money: StubEscrowProvider
) -> None:
    job, escrow = await completed_job(session, worker)
    assert service.job_stage(job, escrow) == "awaiting_confirmation"

    with pytest.raises(service.EscrowStateError):
        await service.release(session, job.id, by="client", code="not a code!")

    await service.release(session, job.id, by="client", code=CLIENT_CODE, now=NOW)

    assert never_move_real_money.applied == [(escrow.provider_transaction_id, CLIENT_CODE)]
    assert escrow.status is EscrowStatus.RELEASED
    assert job.status is JobStatus.RELEASED
    assert service.job_stage(job, escrow) == "released"


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
        await service.release(session, job.id, by="client", code=CLIENT_CODE)

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


async def test_unconfirmed_client_is_reminded_and_money_stays_held(
    session: AsyncSession,
    worker: Worker,
    never_send_real_email: LoggingEmailSender,
    never_move_real_money: StubEscrowProvider,
) -> None:
    job, escrow = await completed_job(session, worker)

    assert await service.remind_unconfirmed(session, now=NOW + timedelta(days=6)) == []
    reminded = await service.remind_unconfirmed(session, now=NOW + timedelta(days=7, hours=1))

    assert reminded == [job.id]
    assert job.confirmation_reminded_at == NOW + timedelta(days=7, hours=1)
    message = never_send_real_email.sent[-1]
    assert message.to == "peter@example.com"
    assert "escrow code" in message.body
    # A reminder, never a payment.
    assert never_move_real_money.applied == []
    assert escrow.status is EscrowStatus.HELD
    assert job.status is JobStatus.SUBMITTED


async def test_reminders_are_sent_once(session: AsyncSession, worker: Worker) -> None:
    await completed_job(session, worker)

    first = await service.remind_unconfirmed(session, now=NOW + timedelta(days=8))
    second = await service.remind_unconfirmed(session, now=NOW + timedelta(days=9))

    assert len(first) == 1
    assert second == []


async def test_disputed_jobs_are_not_reminded(session: AsyncSession, worker: Worker) -> None:
    user = await session.get(User, worker.user_id)
    job, _ = await completed_job(session, worker)
    # Mark complete, then the client side goes wrong: the job is disputed.
    escrow = await service.latest_escrow(session, job.id)
    escrow.in_dispute = True
    await session.flush()

    assert await service.remind_unconfirmed(session, now=NOW + timedelta(days=8)) == []
    assert user is not None
