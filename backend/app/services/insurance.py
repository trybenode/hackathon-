"""Purpose: Price, activate and end the micro-insurance on escrow-protected jobs.

Dependencies: SQLAlchemy async sessions, app.models.domain and app.core.config.
Used by: app.services.escrow, at each step of a job's money.

SRS 3.6: the premium is paid with the escrowed funds (FR-6.2); cover activates
only once that payment is confirmed (FR-6.3, "no premium, no cover"); and it is
voided, or never activated, if the protected flow is abandoned (FR-6.4).
Insurance providers are stubbed (SRS 7), so activation issues our own
reference; a real insurer would bind the policy there instead.
"""

from __future__ import annotations

import uuid
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.domain import EscrowTransaction, InsurancePolicy, InsuranceStatus

PROVIDER = "stub"
CENT = Decimal("0.01")


def premium_for(amount: Decimal) -> Decimal:
    """The client's premium for a job: a share of it, between a floor and a cap."""

    settings = get_settings()
    if settings.insurance_premium_rate <= 0:
        return Decimal("0.00")
    raw = amount * Decimal(str(settings.insurance_premium_rate))
    floor = Decimal(str(settings.insurance_premium_min))
    cap = Decimal(str(settings.insurance_premium_max))
    return min(max(raw, floor), cap).quantize(CENT, rounding=ROUND_HALF_UP)


async def policy_for(session: AsyncSession, job_id: UUID) -> InsurancePolicy | None:
    return await session.scalar(select(InsurancePolicy).where(InsurancePolicy.job_id == job_id))


def quote(session: AsyncSession, job_id: UUID, amount: Decimal, premium: Decimal) -> InsurancePolicy | None:
    """Record the cover a job will have once its premium is paid. Pending until then."""

    if premium <= 0:
        return None
    policy = InsurancePolicy(
        job_id=job_id,
        provider=PROVIDER,
        premium=premium,
        coverage_amount=amount,
        status=InsuranceStatus.PENDING,
    )
    session.add(policy)
    return policy


async def activate(session: AsyncSession, escrow: EscrowTransaction) -> bool:
    """The client's payment, premium included, is confirmed: cover starts."""

    policy = await policy_for(session, escrow.job_id)
    if policy is None or policy.status is not InsuranceStatus.PENDING:
        return False
    policy.status = InsuranceStatus.ACTIVE
    policy.provider_reference = f"COVER-{uuid.uuid4().hex[:10].upper()}"
    escrow.cover_active = True
    return True


async def end(session: AsyncSession, escrow: EscrowTransaction, *, voided: bool) -> None:
    """The job is settled. Voided when the client is refunded (the protected
    flow was abandoned); otherwise the cover simply ran its course."""

    policy = await policy_for(session, escrow.job_id)
    escrow.cover_active = False
    if policy is None or policy.status in {InsuranceStatus.VOIDED, InsuranceStatus.EXPIRED}:
        return
    policy.status = InsuranceStatus.VOIDED if voided else InsuranceStatus.EXPIRED
