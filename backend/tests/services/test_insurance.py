"""Purpose: Verify micro-insurance follows "no premium, no cover" (SRS 3.6).

Dependencies: pytest, SQLAlchemy async sessions, app.services.escrow and insurance.
Used by: the backend test suite and CI. Uses the stub escrow provider.
"""

from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.domain import InsuranceStatus, User, Worker
from app.services import escrow as escrow_service
from app.services import insurance


def job_request(worker: Worker, amount: str = "25000.00") -> escrow_service.JobRequest:
    return escrow_service.JobRequest(
        worker_id=worker.id,
        title="Home cleaning",
        amount=Decimal(amount),
        client_name="Peter James",
        client_email="peter@example.com",
        client_phone="08012345678",
    )


def paid(escrow) -> dict:
    return {
        "transactionId": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
        "transactionNumber": escrow.provider_reference,
        "paymentStatus": "Paid",
        "amountPaid": str(escrow.total_payable),
        "currency": "NGN",
    }


@pytest.mark.parametrize(
    ("amount", "premium"),
    [
        ("25000.00", "500.00"),  # 2%
        ("5000.00", "200.00"),  # floor
        ("500000.00", "2000.00"),  # cap
    ],
)
def test_premium_is_two_percent_between_floor_and_cap(amount: str, premium: str) -> None:
    assert insurance.premium_for(Decimal(amount)) == Decimal(premium)


async def test_client_pays_the_premium_on_top(session: AsyncSession, worker: Worker) -> None:
    job, escrow = await escrow_service.open_job(session, job_request(worker))

    assert escrow.amount == Decimal("25000.00")
    assert escrow.micro_premium == Decimal("500.00")
    assert escrow.total_payable == Decimal("25500.00")
    policy = await insurance.policy_for(session, job.id)
    assert policy.status is InsuranceStatus.PENDING
    assert policy.coverage_amount == Decimal("25000.00")
    # No premium paid yet, so no cover.
    assert escrow.cover_active is False


async def test_cover_activates_only_once_payment_is_confirmed(
    session: AsyncSession, worker: Worker
) -> None:
    job, escrow = await escrow_service.open_job(session, job_request(worker))
    await escrow_service.handle_webhook(session, paid(escrow), delivery_id="d-1")

    policy = await insurance.policy_for(session, job.id)
    assert policy.status is InsuranceStatus.ACTIVE
    assert policy.provider_reference.startswith("COVER-")
    assert escrow.cover_active is True


async def test_short_payment_never_activates_cover(session: AsyncSession, worker: Worker) -> None:
    job, escrow = await escrow_service.open_job(session, job_request(worker))
    # Paid the job but not the premium.
    await escrow_service.handle_webhook(
        session, paid(escrow) | {"amountPaid": "25000.00"}, delivery_id="d-short"
    )

    assert (await insurance.policy_for(session, job.id)).status is InsuranceStatus.PENDING
    assert escrow.cover_active is False


async def test_refund_voids_the_cover(session: AsyncSession, worker: Worker) -> None:
    user = await session.get(User, worker.user_id)
    job, escrow = await escrow_service.open_job(session, job_request(worker))
    await escrow_service.handle_webhook(session, paid(escrow), delivery_id="d-2")
    await escrow_service.report_issue(session, user, job.id, reason="Work conditions changed", complaint="")

    await escrow_service.handle_webhook(
        session,
        {
            "event": "dispute.status_changed",
            "eventId": "e-1",
            "transactionNumber": escrow.provider_reference,
            "disputeStage": "Resolved",
            "resolutionType": "Refund",
        },
        delivery_id="e-1",
    )

    assert (await insurance.policy_for(session, job.id)).status is InsuranceStatus.VOIDED
    assert escrow.cover_active is False


async def test_cover_ends_when_the_job_is_paid_out(session: AsyncSession, worker: Worker) -> None:
    user = await session.get(User, worker.user_id)
    job, escrow = await escrow_service.open_job(session, job_request(worker))
    await escrow_service.handle_webhook(session, paid(escrow), delivery_id="d-3")
    await escrow_service.mark_complete(session, user, job.id)

    await escrow_service.release(session, job.id, by="client", code="XYZ789ABC1")

    assert (await insurance.policy_for(session, job.id)).status is InsuranceStatus.EXPIRED
    assert escrow.cover_active is False


async def test_premium_can_be_turned_off(
    session: AsyncSession, worker: Worker, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(get_settings(), "insurance_premium_rate", 0)

    job, escrow = await escrow_service.open_job(session, job_request(worker))

    assert escrow.micro_premium == Decimal("0.00")
    assert escrow.total_payable == Decimal("25000.00")
    assert await insurance.policy_for(session, job.id) is None
