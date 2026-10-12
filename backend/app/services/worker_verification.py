"""Purpose: Summarise what has been verified about a worker, for platforms.

Dependencies: SQLAlchemy async sessions, app.models.domain, and the identity
check helpers in app.services.worker_record.
Used by: the trust query, so one call answers both "how trustworthy" (the
score) and "who is this" (identity, liveness, guarantor).

Only outcomes of checks are shared: never identity numbers or documents.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.domain import AgreementStatus, GuarantorAgreement, Worker
from app.services.worker_record import check_status, latest_check

WAITING = (AgreementStatus.PENDING_SIGNATURE, AgreementStatus.PENDING_VERIFICATION)


@dataclass(frozen=True)
class WorkerVerification:
    #: "verified", "sandbox" (a stand-in provider passed it) or "not_verified".
    identity: str
    liveness: str
    #: "active", "pending" (asked, not yet live) or "none".
    guarantor: str
    #: When the active guarantee runs out.
    guarantor_valid_until: datetime | None


def _as_aware(moment: datetime) -> datetime:
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)


async def verification_for(
    session: AsyncSession, worker: Worker, *, now: datetime | None = None
) -> WorkerVerification:
    moment = now or datetime.now(UTC)
    agreements = (
        await session.scalars(
            select(GuarantorAgreement)
            .where(
                GuarantorAgreement.worker_id == worker.id,
                GuarantorAgreement.status.in_((AgreementStatus.ACTIVE, *WAITING)),
            )
            .order_by(GuarantorAgreement.valid_until.desc())
        )
    ).all()
    live = [item for item in agreements if _as_aware(item.valid_until) > moment]
    active = next((item for item in live if item.status is AgreementStatus.ACTIVE), None)
    return WorkerVerification(
        identity=check_status(await latest_check(session, worker.user_id, "identity")),
        liveness=check_status(await latest_check(session, worker.user_id, "liveness")),
        guarantor="active" if active else "pending" if live else "none",
        guarantor_valid_until=_as_aware(active.valid_until) if active else None,
    )


async def verification_for_id(session: AsyncSession, worker_id: UUID) -> WorkerVerification | None:
    worker = await session.get(Worker, worker_id)
    return await verification_for(session, worker) if worker else None
