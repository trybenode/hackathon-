"""Purpose: Verify the freelance job flow: link, payment, completion, release, disputes.

Dependencies: pytest, SQLAlchemy async sessions, and app.services.escrow.
Used by: the backend test suite and CI. Uses the stub provider and the logging
email sender throughout.
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.domain import (
    DisputeStatus,
    EscrowStatus,
    JobStatus,
    NormalizedOutcome,
    OutcomeStatus,
    User,
    Worker,
)
from app.services import escrow as service
from app.services.email_sender import LoggingEmailSender
from app.services.escrow_provider import StubEscrowProvider

NOW = datetime(2026, 10, 10, 12, 0, tzinfo=UTC)
CODE = "XYZ789ABC1"


async def worker_user(session: AsyncSession, worker: Worker) -> User:
    return await session.get(User, worker.user_id)


async def job_link(session: AsyncSession, worker: Worker):
    return await service.create_job_link(
        session,
        await worker_user(session, worker),
        title="Home cleaning",
        address="Lagos Island, Lagos",
        scheduled_at=NOW + timedelta(days=3),
        price=Decimal("25000.00"),
    )


async def paid_job(session: AsyncSession, worker: Worker):
    job = await job_link(session, worker)
    escrow = await service.start_payment(
        session, job.link_token, name="Sarah Ade", email="sarah@example.com", phone="08012345678"
    )
    await service.handle_webhook(
        session,
        {
            "transactionId": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
            "transactionNumber": escrow.provider_reference,
            "paymentStatus": "Paid",
            "amountPaid": str(escrow.total_payable),
            "currency": "NGN",
        },
        delivery_id=f"paid-{job.id}",
    )
    return job, escrow


async def completed_job(session: AsyncSession, worker: Worker, *, at: datetime = NOW):
    job, escrow = await paid_job(session, worker)
    await service.mark_complete(session, await worker_user(session, worker), job.id, now=at)
    return job, escrow


async def test_worker_creates_a_job_link(session: AsyncSession, worker: Worker) -> None:
    job = await job_link(session, worker)

    assert job.status is JobStatus.DRAFT
    assert len(job.link_token) >= 20
    assert job.location == "Lagos Island, Lagos"
    assert service.job_stage(job, None) == "awaiting_customer"


async def test_worker_without_a_phone_cannot_create_a_link(
    session: AsyncSession, worker: Worker
) -> None:
    user = await worker_user(session, worker)
    user.phone = None
    await session.flush()

    with pytest.raises(service.EscrowStateError, match="phone number"):
        await job_link(session, worker)


async def test_customer_pays_into_escrow(session: AsyncSession, worker: Worker) -> None:
    job = await job_link(session, worker)

    escrow = await service.start_payment(
        session, job.link_token, name="Sarah Ade", email="sarah@example.com", phone="08012345678"
    )

    assert job.status is JobStatus.ACCEPTED
    assert job.client_email == "sarah@example.com"
    assert escrow.status is EscrowStatus.PENDING
    assert escrow.total_payable == Decimal("25500.00")  # job + 2% protection
    # Asking again before paying gives the same order, not a second one.
    again = await service.start_payment(
        session, job.link_token, name="Sarah Ade", email="sarah@example.com", phone="08012345678"
    )
    assert again.id == escrow.id


async def test_customer_email_must_differ_from_the_workers(
    session: AsyncSession, worker: Worker
) -> None:
    job = await job_link(session, worker)

    with pytest.raises(service.EscrowStateError, match="differ"):
        await service.start_payment(
            session, job.link_token, name="Jane", email="worker@example.com", phone="08012345678"
        )


async def test_invalid_link_is_not_found(session: AsyncSession) -> None:
    with pytest.raises(service.JobNotFoundError):
        await service.job_by_token(session, "nope")


async def test_payment_holds_the_money_and_tells_the_worker(
    session: AsyncSession, worker: Worker, never_send_real_email: LoggingEmailSender
) -> None:
    job, escrow = await paid_job(session, worker)

    assert escrow.status is EscrowStatus.HELD
    assert job.status is JobStatus.IN_PROGRESS
    assert service.job_stage(job, escrow) == "held"
    assert never_send_real_email.sent[-1].to == "worker@example.com"
    assert "Payment received" in never_send_real_email.sent[-1].subject


async def test_short_payment_is_not_treated_as_paid(session: AsyncSession, worker: Worker) -> None:
    job = await job_link(session, worker)
    escrow = await service.start_payment(
        session, job.link_token, name="Sarah", email="sarah@example.com", phone="08012345678"
    )

    outcome = await service.handle_webhook(
        session,
        {"transactionId": "x", "transactionNumber": escrow.provider_reference,
         "paymentStatus": "Paid", "amountPaid": "100.00", "currency": "NGN"},
        delivery_id="short",
    )

    assert outcome == "amount mismatch"
    assert escrow.status is EscrowStatus.PENDING


async def test_completion_emails_the_customer_their_job_page(
    session: AsyncSession, worker: Worker, never_send_real_email: LoggingEmailSender
) -> None:
    job, escrow = await completed_job(session, worker)

    assert service.job_stage(job, escrow) == "awaiting_confirmation"
    message = never_send_real_email.sent[-1]
    assert message.to == "sarah@example.com"
    assert f"/j/{job.link_token}" in message.body
    assert "48 hours" in message.body


async def test_customer_releases_with_code_and_rating(
    session: AsyncSession,
    worker: Worker,
    never_move_real_money: StubEscrowProvider,
    never_send_real_email: LoggingEmailSender,
) -> None:
    job, escrow = await completed_job(session, worker)

    with pytest.raises(service.EscrowStateError, match="stars"):
        await service.release_by_customer(session, job.link_token, code=CODE, rating=0)
    with pytest.raises(service.EscrowCodeMissingError):
        await service.release_by_customer(session, job.link_token, code="", rating=5)

    await service.release_by_customer(session, job.link_token, code=CODE, rating=5, now=NOW)

    assert never_move_real_money.applied == [(escrow.provider_transaction_id, CODE)]
    assert escrow.status is EscrowStatus.RELEASED
    assert job.status is JobStatus.RELEASED
    assert job.rating == 5
    assert "released" in never_send_real_email.sent[-1].subject.lower()

    # The released job and its rating feed the trust score.
    outcome = await session.scalar(select(NormalizedOutcome).where(NormalizedOutcome.job_id == job.id))
    assert outcome.verified and outcome.status is OutcomeStatus.COMPLETED
    assert outcome.rating == Decimal(5)
    assert outcome.completion_confirmed


async def test_customer_reports_a_problem(
    session: AsyncSession, worker: Worker, never_move_real_money: StubEscrowProvider,
    never_send_real_email: LoggingEmailSender,
) -> None:
    job, escrow = await paid_job(session, worker)

    dispute = await service.report_issue_by_customer(
        session, job.link_token, reason="Damaged or missing items", complaint="Vase broken",
        evidence=["dispute-evidence/x/photo.jpg"],
    )

    assert never_move_real_money.disputes[0][1] == "customer"
    assert dispute.raised_by == "customer" and dispute.opened_by_id is None
    assert dispute.evidence_urls == ["dispute-evidence/x/photo.jpg"]
    assert service.job_stage(job, escrow) == "disputed"
    recipients = {message.to for message in never_send_real_email.sent[-2:]}
    assert recipients == {"sarah@example.com", "worker@example.com"}
    with pytest.raises(service.EscrowStateError):
        await service.release_by_customer(session, job.link_token, code=CODE, rating=5)


async def test_worker_reports_an_issue(
    session: AsyncSession, worker: Worker, never_move_real_money: StubEscrowProvider
) -> None:
    job, _ = await paid_job(session, worker)

    dispute = await service.report_issue_by_worker(
        session, await worker_user(session, worker), job.id,
        reason="Client didn't provide required access", complaint="",
    )

    assert dispute.raised_by == "worker"
    assert never_move_real_money.disputes[0][1] == "merchant"


async def test_no_code_within_48_hours_opens_a_dispute(
    session: AsyncSession, worker: Worker, never_move_real_money: StubEscrowProvider
) -> None:
    job, escrow = await completed_job(session, worker)

    assert await service.dispute_overdue_confirmations(session, now=NOW + timedelta(hours=47)) == []
    opened = await service.dispute_overdue_confirmations(session, now=NOW + timedelta(hours=49))

    assert opened == [job.id]
    dispute = await service.latest_dispute(session, job.id)
    assert dispute.raised_by == "timeout"
    assert never_move_real_money.disputes[0][1] == "merchant"
    # A dispute, never a payment.
    assert never_move_real_money.applied == []
    assert escrow.status is EscrowStatus.HELD


async def test_ruling_refund_records_an_upheld_outcome(session: AsyncSession, worker: Worker) -> None:
    job, escrow = await paid_job(session, worker)
    await service.report_issue_by_customer(session, job.link_token, reason="Worker didn't show up", complaint="")

    await service.handle_webhook(
        session,
        {"event": "dispute.status_changed", "eventId": "e-1",
         "transactionNumber": escrow.provider_reference, "disputeStage": "Resolved",
         "resolutionType": "Refund", "inDispute": False},
        delivery_id="e-1",
    )

    assert escrow.status is EscrowStatus.REFUNDED
    assert job.status is JobStatus.CANCELLED
    assert (await service.latest_dispute(session, job.id)).status is DisputeStatus.RESOLVED
    outcome = await session.scalar(select(NormalizedOutcome).where(NormalizedOutcome.job_id == job.id))
    assert outcome.dispute_resolution == "upheld"


async def test_ruling_close_pays_the_worker(session: AsyncSession, worker: Worker) -> None:
    job, escrow = await paid_job(session, worker)
    await service.report_issue_by_worker(
        session, await worker_user(session, worker), job.id, reason="Payment-related issue", complaint=""
    )

    await service.handle_webhook(
        session,
        {"event": "dispute.status_changed", "eventId": "e-2",
         "transactionNumber": escrow.provider_reference, "disputeStage": "Resolved",
         "resolutionType": "Close"},
        delivery_id="e-2",
    )

    assert escrow.status is EscrowStatus.RELEASED
    assert job.status is JobStatus.RELEASED


async def test_someone_elses_job_is_not_found(session: AsyncSession, worker: Worker) -> None:
    stranger = User(email="stranger@example.com", display_name="Stranger")
    session.add(stranger)
    await session.flush()
    job, _ = await paid_job(session, worker)

    with pytest.raises(service.JobNotFoundError):
        await service.mark_complete(session, stranger, job.id)


async def test_missing_webhook_is_caught_by_checking_payscrow(
    session: AsyncSession, worker: Worker, never_move_real_money: StubEscrowProvider
) -> None:
    """Payscrow's guide, step 8: if the paid webhook never comes, read the status."""

    job = await job_link(session, worker)
    escrow = await service.start_payment(
        session, job.link_token, name="Sarah Ade", email="sarah@example.com", phone="08012345678"
    )
    assert await service.sync_payment(session, job, escrow) is False  # not paid yet

    never_move_real_money.paid.add(escrow.provider_reference)
    assert await service.sync_payment(session, job, escrow) is True

    assert escrow.status is EscrowStatus.HELD
    assert job.status is JobStatus.IN_PROGRESS
    # The status check has no transaction GUID, so release waits for the webhook.
    await service.mark_complete(session, await worker_user(session, worker), job.id)
    with pytest.raises(service.EscrowStateError, match="confirmation has not reached us"):
        await service.release_by_customer(session, job.link_token, code="5Z093S", rating=5)


async def test_six_character_codes_are_accepted(
    session: AsyncSession, worker: Worker, never_move_real_money: StubEscrowProvider
) -> None:
    job, escrow = await completed_job(session, worker)

    await service.release_by_customer(session, job.link_token, code="5Z093S", rating=4)

    assert never_move_real_money.applied[-1] == (escrow.provider_transaction_id, "5Z093S")
