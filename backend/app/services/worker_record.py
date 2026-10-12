"""One evidence snapshot for private worker records and public projections."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.domain import AgreementStatus, GuarantorAgreement, IdentityVerification, Job, JobConfirmation, JobStatus, NormalizedOutcome, OutcomeStatus, TrustAssessment, User, Worker
from app.services.trust_scoring.assessment import assess_worker
from app.services.trust_scoring.evidence import scoring_inputs
from app.services.trust_scoring.scoring import starting_rating
from app.services.trust_scoring.signals import aggregate

RECORD_PLATFORM_TYPE = "generic"
PREVIEW_SIZE = 20


class NotAWorkerError(Exception):
    """The signed-in user has no active worker profile."""


@dataclass(frozen=True)
class RecordOutcome:
    id: UUID
    title: str
    occurred_at: datetime
    amount: Decimal | None
    status: str
    location: str | None = None
    client_name: str | None = None
    #: The customer's 1-5 stars, given when they released the payment.
    rating: float | None = None
    #: "none", or how a dispute on this job ended: "dismissed" or "upheld".
    dispute: str = "none"
    #: Where the outcome was verified: "native" here, else the importing platform.
    source: str = "native"


@dataclass(frozen=True)
class IdentityCredential:
    nin_verified: bool
    bvn_verified: bool
    verified_at: datetime
    status: str


@dataclass(frozen=True)
class GuarantorCredential:
    name: str
    verified: bool
    status: str
    activated_at: datetime
    valid_until: datetime
    sandbox: bool
    #: How the guarantor knows the worker, e.g. "employer".
    relationship: str = ""


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
    location: str | None
    identity_verified: bool
    identity_status: str
    decision: bool
    confidence: Decimal
    band: str
    status: str
    signals_used: list[str]
    explanation_summary: str
    score: float | None
    verified_outcomes: int
    self_declared_outcomes: int
    total_outcomes: int
    last_updated: datetime
    assessed_at: datetime
    completed_jobs: int
    completion_rate: float | None
    repeat_hires: int | None
    disputes: int | None
    outcomes: list[RecordOutcome]
    identity: IdentityCredential | None
    guarantor: GuarantorCredential | None
    imported_record: ImportedRecordCredential | None
    starting_rating: float | None
    starting_rating_label: str | None


def _as_aware(moment: datetime) -> datetime:
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)


async def latest_check(session: AsyncSession, user_id: UUID, check_type: str = "identity") -> IdentityVerification | None:
    """Select the latest check, including failures that supersede earlier passes."""
    return await session.scalar(select(IdentityVerification).where(IdentityVerification.user_id == user_id, IdentityVerification.check_type == check_type).order_by(IdentityVerification.created_at.desc(), IdentityVerification.id.desc()).limit(1))


def check_status(check: IdentityVerification | None) -> str:
    """Distinguish actual provider verification from successful sandbox checks."""
    if check is None or check.status != "verified":
        return "not_verified"
    return "sandbox" if check.provider == "stub" else "verified"


async def _identity(session: AsyncSession, user_id: UUID) -> IdentityCredential | None:
    check = await latest_check(session, user_id)
    if check is None:
        return None
    # The stored provider result does not identify individual NIN/BVN checks.
    return IdentityCredential(False, False, _as_aware(check.created_at), check_status(check))


async def _guarantor(session: AsyncSession, worker_id: UUID) -> GuarantorCredential | None:
    agreement = await session.scalar(select(GuarantorAgreement).where(GuarantorAgreement.worker_id == worker_id, GuarantorAgreement.verified_at.is_not(None)).order_by(GuarantorAgreement.verified_at.desc(), GuarantorAgreement.id.desc()).limit(1))
    if agreement is None:
        return None
    person = await session.get(User, agreement.guarantor_user_id)
    checks = [check_status(await latest_check(session, agreement.guarantor_user_id, kind)) for kind in ("identity", "liveness")]
    status = agreement.status.value
    if agreement.status == AgreementStatus.ACTIVE and _as_aware(agreement.valid_until) <= datetime.now(UTC):
        status = AgreementStatus.EXPIRED.value
    return GuarantorCredential(person.display_name if person else "", all(value == "verified" for value in checks), status.replace("_", " ").title(), _as_aware(agreement.verified_at), _as_aware(agreement.valid_until), all(value in {"verified", "sandbox"} for value in checks) and any(value == "sandbox" for value in checks), agreement.relationship_type)


async def completion_labels(session: AsyncSession, rows: list[NormalizedOutcome]) -> dict[UUID, str]:
    """Label completion from attributable confirmations, never a default boolean."""
    job_ids = {row.job_id for row in rows if row.job_id}
    jobs = {job.id: job for job in (await session.scalars(select(Job).where(Job.id.in_(job_ids)))).all()} if job_ids else {}
    confirmed = set((await session.scalars(select(JobConfirmation.job_id).join(Job, Job.id == JobConfirmation.job_id).where(Job.id.in_(job_ids), JobConfirmation.confirmer_role == "client", JobConfirmation.confirmer_id == Job.client_id, JobConfirmation.confirmed.is_(True), JobConfirmation.confirmed_at <= datetime.now(UTC)))).all()) if job_ids else set()
    return {row.id: ("Client Confirmed" if row.job_id in confirmed else "Released" if row.job_id in jobs and jobs[row.job_id].status == JobStatus.RELEASED else "Completion unconfirmed" if row.job_id in jobs else "Recorded work" if row.verified else "Self-declared record") for row in rows}


async def _record_outcomes(session: AsyncSession, rows: list[NormalizedOutcome]) -> list[RecordOutcome]:
    """Completed outcomes as the record lists them: the job, where, who, rating and dispute."""
    if not rows:
        return []
    jobs = {job.id: job for job in (await session.scalars(select(Job).where(Job.id.in_({item.job_id for item in rows if item.job_id})))).all()}
    labels = await completion_labels(session, rows)
    return [RecordOutcome(row.id, jobs[row.job_id].title if row.job_id in jobs else "Recorded job", _as_aware(row.occurred_at), row.amount if row.amount is not None else jobs[row.job_id].agreed_amount if row.job_id in jobs else None, labels[row.id],
        location=jobs[row.job_id].location if row.job_id in jobs else None,
        client_name=jobs[row.job_id].client_name if row.job_id in jobs else None,
        rating=float(row.rating) if row.rating is not None else None,
        dispute=row.dispute_resolution if row.dispute_resolution in ("dismissed", "upheld") else "none",
        source=row.source_platform) for row in rows]


async def completed_outcomes(session: AsyncSession, user: User, *, page: int = 1, size: int = PREVIEW_SIZE) -> tuple[list[RecordOutcome], int]:
    """Every completed verified outcome, a page at a time; the record shows only the first page."""
    worker = await session.scalar(select(Worker).where(Worker.user_id == user.id))
    if worker is None or not user.is_active:
        raise NotAWorkerError("This account has no active worker profile.")
    rows = list((await session.scalars(select(NormalizedOutcome).where(NormalizedOutcome.worker_id == worker.id, NormalizedOutcome.verified.is_(True)).order_by(NormalizedOutcome.occurred_at.desc(), NormalizedOutcome.id))).all())
    inputs = await scoring_inputs(session, rows)
    completed = [row for row, evidence in zip(rows, inputs, strict=True) if row.status == OutcomeStatus.COMPLETED and "completion_rate" in evidence["available_signals"]]
    return await _record_outcomes(session, completed[(page - 1) * size : page * size]), len(completed)


async def load_record(session: AsyncSession, user: User, *, include_history: bool = True, include_starting_history: bool = True) -> WorkerRecord:
    """Build shared evidence semantics; public callers skip private history work."""
    worker = await session.scalar(select(Worker).where(Worker.user_id == user.id).with_for_update())
    if worker is None or not user.is_active:
        raise NotAWorkerError("This account has no active worker profile.")
    assessment = await assess_worker(session, worker.id, RECORD_PLATFORM_TYPE)
    stored = await session.get(TrustAssessment, assessment.id)
    total = await session.scalar(select(func.count()).select_from(NormalizedOutcome).where(NormalizedOutcome.worker_id == worker.id))
    rows = list((await session.scalars(select(NormalizedOutcome).where(NormalizedOutcome.worker_id == worker.id, NormalizedOutcome.verified.is_(True)).order_by(NormalizedOutcome.occurred_at.desc(), NormalizedOutcome.id))).all())
    inputs = await scoring_inputs(session, rows)
    completed = [row for row, evidence in zip(rows, inputs, strict=True) if row.status == OutcomeStatus.COMPLETED and "completion_rate" in evidence["available_signals"]]
    responsible = [item for item in inputs if "completion_rate" in item["available_signals"] and not (item["status"] == "cancelled" and item["cancelled_by"] in {"client", "platform"})]
    known_clients = [item["client_id"] for item in inputs if item["client_id"]]
    known_disputes = [item for item in inputs if "dispute_rate" in item["available_signals"]]
    preview = completed[:PREVIEW_SIZE] if include_history else []
    history = await _record_outcomes(session, preview)
    imported_count, imported_at = (await session.execute(select(func.count(NormalizedOutcome.id), func.max(NormalizedOutcome.created_at)).where(NormalizedOutcome.worker_id == worker.id, NormalizedOutcome.verified.is_(True), NormalizedOutcome.import_method != "native"))).one()
    initial = None
    if include_starting_history and total > len(rows):
        imported = list((await session.scalars(select(NormalizedOutcome).where(NormalizedOutcome.worker_id == worker.id, NormalizedOutcome.verified.is_(False)))).all())
        signals, count = aggregate(await scoring_inputs(session, imported), {"completion_rate", "cancellation_rate"})
        if signals:
            initial = starting_rating(signals, count)
    identity = await _identity(session, user.id)
    return WorkerRecord(worker_id=worker.id, name=user.display_name, role=worker.role, avatar_url=worker.avatar_url, location=worker.location,
        identity_verified=bool(identity and identity.status == "verified"), identity_status=identity.status if identity else "not_verified",
        decision=assessment.decision, confidence=assessment.confidence, band=assessment.band, status=assessment.status, signals_used=assessment.signals_used, explanation_summary=assessment.explanation_summary, score=float(assessment.score) if assessment.score is not None else None,
        verified_outcomes=len(rows), self_declared_outcomes=total-len(rows), total_outcomes=total, last_updated=datetime.now(UTC), assessed_at=_as_aware(stored.assessed_at),
        completed_jobs=len(completed), completion_rate=sum(item["status"] == "completed" for item in responsible)/len(responsible) if responsible else None,
        repeat_hires=len(known_clients)-len(set(known_clients)) if known_clients else None, disputes=sum(item["dispute_resolution"] in {"open", "upheld"} for item in known_disputes) if known_disputes else None,
        outcomes=history, identity=identity, guarantor=await _guarantor(session, worker.id), imported_record=ImportedRecordCredential(imported_count, _as_aware(imported_at)) if imported_count else None,
        starting_rating=initial["starting_rating"] if initial else None, starting_rating_label=initial["label"] if initial else None)
