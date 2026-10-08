"""Purpose: Assemble a worker's own portable record from stored history.

Dependencies: SQLAlchemy async sessions, app.models.domain, and the shared
trust assessment service.
Used by: the worker profile, portable record, outcomes and credentials screens.

The trust band comes from `assess_worker()`, the one scoring path every caller
shares; nothing here scores a worker itself.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.domain import (
    AgreementStatus,
    GuarantorAgreement,
    IdentityVerification,
    Job,
    NormalizedOutcome,
    OutcomeStatus,
    TrustAssessment,
    User,
    Worker,
)
from app.services.trust_scoring.assessment import assess_worker

#: Scoring preset for the worker's own view. Platforms pick theirs when they
#: query; the record a worker carries is scored on the generic preset.
RECORD_PLATFORM_TYPE = "generic"

#: How imported outcomes are marked by the credentials import.
IMPORTED = "api"

#: A guarantee in one of these states still stands behind the worker.
LIVE_GUARANTEE = {
    AgreementStatus.ACTIVE,
    AgreementStatus.TRIGGERED,
    AgreementStatus.DISPUTED,
    AgreementStatus.SUSPENDED,
}


class NotAWorkerError(Exception):
    """The signed-in user has no worker profile."""


@dataclass(frozen=True)
class RecordOutcome:
    id: UUID
    title: str
    occurred_at: datetime
    amount: Decimal | None
    #: "Client Confirmed" when the client signed off, else "Auto-released".
    status: str


@dataclass(frozen=True)
class IdentityCredential:
    nin_verified: bool
    bvn_verified: bool
    verified_at: datetime


@dataclass(frozen=True)
class GuarantorCredential:
    name: str
    verified: bool
    status: str
    activated_at: datetime
    valid_until: datetime


@dataclass(frozen=True)
class ImportedRecordCredential:
    verified_outcomes: int
    updated_at: datetime


@dataclass(frozen=True)
class WorkerRecord:
    worker_id: UUID
    name: str
    role: str | None
    avatar_url: str | None
    identity_verified: bool
    decision: bool
    confidence: Decimal
    band: str
    status: str
    signals_used: list[str]
    explanation_summary: str
    #: The "Trust Score" ring, 0 to 1; None while building history.
    score: float | None
    verified_outcomes: int
    last_updated: datetime
    completed_jobs: int
    #: Completed share of jobs the worker was responsible for.
    completion_rate: float | None
    repeat_hires: int
    disputes: int
    outcomes: list[RecordOutcome]
    identity: IdentityCredential | None
    guarantor: GuarantorCredential | None
    imported_record: ImportedRecordCredential | None


def _as_aware(moment: datetime) -> datetime:
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)


def _responsible(outcome: NormalizedOutcome) -> bool:
    """Jobs the worker answers for: a client or platform cancelling is not on them."""

    return not (
        outcome.status is OutcomeStatus.CANCELLED and outcome.cancelled_by in {"client", "platform"}
    )


def _repeat_hires(outcomes: list[NormalizedOutcome]) -> int:
    """Jobs from a client who had hired the worker before."""

    seen: set[str] = set()
    repeats = 0
    for outcome in sorted(outcomes, key=lambda item: _as_aware(item.occurred_at)):
        if not outcome.client_id:
            continue
        if outcome.client_id in seen:
            repeats += 1
        seen.add(outcome.client_id)
    return repeats


async def _identity(session: AsyncSession, user_id: UUID) -> IdentityCredential | None:
    check = await session.scalar(
        select(IdentityVerification)
        .where(
            IdentityVerification.user_id == user_id,
            IdentityVerification.check_type == "identity",
            IdentityVerification.status == "verified",
        )
        .order_by(IdentityVerification.created_at.desc())
    )
    if check is None:
        return None
    # The provider checks NIN and BVN together, so one pass covers both.
    return IdentityCredential(
        nin_verified=True, bvn_verified=True, verified_at=_as_aware(check.created_at)
    )


async def _guarantor(session: AsyncSession, worker_id: UUID) -> GuarantorCredential | None:
    """The worker's most recent guarantee that went live, if any."""

    agreement = await session.scalar(
        select(GuarantorAgreement)
        .where(
            GuarantorAgreement.worker_id == worker_id,
            GuarantorAgreement.verified_at.is_not(None),
        )
        .order_by(GuarantorAgreement.verified_at.desc())
    )
    if agreement is None:
        return None

    person = await session.get(User, agreement.guarantor_user_id)
    return GuarantorCredential(
        name=person.display_name if person else "",
        # A guarantee only goes live once its guarantor passes both checks.
        verified=True,
        status="Active" if agreement.status in LIVE_GUARANTEE else "Expired",
        activated_at=_as_aware(agreement.verified_at),
        valid_until=_as_aware(agreement.valid_until),
    )


async def load_record(session: AsyncSession, user: User) -> WorkerRecord:
    worker = await session.scalar(select(Worker).where(Worker.user_id == user.id))
    if worker is None:
        raise NotAWorkerError("This account has no worker profile.")

    assessment = await assess_worker(session, worker.id, RECORD_PLATFORM_TYPE)
    stored = await session.get(TrustAssessment, assessment.id)

    outcomes = list(
        (
            await session.scalars(
                select(NormalizedOutcome)
                .where(
                    NormalizedOutcome.worker_id == worker.id,
                    NormalizedOutcome.verified.is_(True),
                )
                .order_by(NormalizedOutcome.occurred_at.desc())
            )
        ).all()
    )
    completed = [item for item in outcomes if item.status is OutcomeStatus.COMPLETED]
    responsible = [item for item in outcomes if _responsible(item)]

    jobs = {
        job.id: job
        for job in (
            await session.scalars(
                select(Job).where(Job.id.in_({item.job_id for item in completed if item.job_id}))
            )
        ).all()
    }
    history = [
        RecordOutcome(
            id=item.id,
            title=jobs[item.job_id].title if item.job_id in jobs else "Completed job",
            occurred_at=_as_aware(item.occurred_at),
            amount=item.amount
            if item.amount is not None
            else (jobs[item.job_id].agreed_amount if item.job_id in jobs else None),
            status="Client Confirmed" if item.completion_confirmed else "Auto-released",
        )
        for item in completed
    ]

    imported = [item for item in outcomes if item.import_method == IMPORTED]
    identity = await _identity(session, user.id)

    return WorkerRecord(
        worker_id=worker.id,
        name=user.display_name,
        role=worker.role,
        avatar_url=worker.avatar_url,
        identity_verified=identity is not None,
        decision=assessment.decision,
        confidence=assessment.confidence,
        band=assessment.band,
        status=assessment.status,
        signals_used=assessment.signals_used,
        explanation_summary=assessment.explanation_summary,
        score=float(assessment.score) if assessment.score is not None else None,
        verified_outcomes=len(outcomes),
        last_updated=_as_aware(stored.assessed_at) if stored else datetime.now(tz=UTC),
        completed_jobs=len(completed),
        completion_rate=len(completed) / len(responsible) if responsible else None,
        repeat_hires=_repeat_hires(outcomes),
        disputes=sum(item.dispute_resolution in {"open", "upheld"} for item in outcomes),
        outcomes=history,
        identity=identity,
        guarantor=await _guarantor(session, worker.id),
        imported_record=ImportedRecordCredential(
            verified_outcomes=len(imported),
            updated_at=max(_as_aware(item.created_at) for item in imported),
        )
        if imported
        else None,
    )
