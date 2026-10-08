"""Purpose: Move a job's money through escrow, from payment to release or dispute.

Dependencies: SQLAlchemy async sessions, app.models.domain, and the escrow
provider seam (Payscrow, or the local stand-in).
Used by: the jobs, worker jobs and Payscrow webhook endpoints, and the sweep.

The lifecycle (SRS 3.6):
  open      -> job Accepted, escrow Pending: the client gets a payment link.
  paid      -> job In Progress, escrow Held (Payscrow's webhook says so).
  complete  -> job Submitted: the worker says the work is done; the client has
               ESCROW_AUTO_RELEASE_HOURS to confirm or object.
  release   -> job Released, escrow Released: the client confirmed, or the
               window passed. Releasing applies Payscrow's escrow code.

The escrow code belongs to the paying client: Payscrow sends it to them, and
handing it over is how they confirm (Payscrow's integration guide, step 9). A
client confirms by giving us the code. If Payscrow is set to include the code
in its paid webhook, we already hold it, so confirming needs no code and the
auto-release window can run; otherwise nothing releases without the client.
  dispute   -> job Disputed: raised through Payscrow, whose ruling arrives by
               webhook (Refund, Split or Close).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.domain import (
    AuditEvent,
    Dispute,
    DisputeStatus,
    EscrowStatus,
    EscrowTransaction,
    Job,
    JobStatus,
    JobType,
    Organization,
    OrganizationType,
    ProviderOperation,
    ProviderOperationStatus,
    User,
    Worker,
)
from app.services import escrow_provider as provider_module
from app.services.escrow_provider import EscrowParty, EscrowProvider, EscrowStart

#: Payscrow's code is 10 alphanumerics; anything else in that field (e.g. its
#: "restricted" notice when code-in-webhook is off) is not a code.
ESCROW_CODE = re.compile(r"^[A-Za-z0-9]{6,20}$")

#: Payscrow's complaint length limits.
COMPLAINT_MIN, COMPLAINT_MAX = 10, 1000


class EscrowError(Exception):
    """Base class for escrow failures."""


class JobNotFoundError(EscrowError):
    """No such job, or not this worker's."""


class EscrowStateError(EscrowError):
    """The job's money is not in a state that allows this."""


class EscrowCodeMissingError(EscrowError):
    """The funds cannot be released until Payscrow's escrow code is known."""


@dataclass(frozen=True)
class JobRequest:
    """A job a platform asks us to protect with escrow."""

    worker_id: UUID
    title: str
    amount: Decimal
    client_name: str
    client_email: str
    client_phone: str | None = None
    location: str | None = None
    details: list[dict[str, str]] = field(default_factory=list)
    return_url: str | None = None


def _now() -> datetime:
    return datetime.now(tz=UTC)


def _as_aware(moment: datetime) -> datetime:
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)


def _provider(provider: EscrowProvider | None) -> EscrowProvider:
    # Resolved at call time so tests can swap the module default.
    return provider or provider_module.default_escrow_provider


def _audit(session: AsyncSession, job: Job, action: str, **metadata: Any) -> None:
    session.add(
        AuditEvent(entity_type="job", entity_id=job.id, action=action, event_metadata=metadata)
    )


async def _client_organization(session: AsyncSession) -> Organization:
    """Independent jobs hang off one placeholder organization until clients
    have accounts of their own."""

    organization = await session.scalar(
        select(Organization).where(Organization.name == "Independent clients")
    )
    if organization is None:
        organization = Organization(
            name="Independent clients", organization_type=OrganizationType.EMPLOYER
        )
        session.add(organization)
        await session.flush()
    return organization


async def latest_escrow(session: AsyncSession, job_id: UUID) -> EscrowTransaction | None:
    return await session.scalar(
        select(EscrowTransaction)
        .where(EscrowTransaction.job_id == job_id)
        .order_by(EscrowTransaction.created_at.desc())
    )


async def open_job(
    session: AsyncSession,
    request: JobRequest,
    *,
    provider: EscrowProvider | None = None,
) -> tuple[Job, EscrowTransaction]:
    """Create the job and open its escrow; the client pays via the link."""

    worker = await session.get(Worker, request.worker_id)
    if worker is None:
        raise JobNotFoundError(f"No worker with id {request.worker_id}.")
    person = await session.get(User, worker.user_id)

    job = Job(
        worker_id=worker.id,
        organization_id=(await _client_organization(session)).id,
        job_type=JobType.INDEPENDENT,
        status=JobStatus.ACCEPTED,
        title=request.title,
        agreed_amount=request.amount,
        client_name=request.client_name,
        client_email=request.client_email,
        client_phone=request.client_phone,
        location=request.location,
        details=request.details,
    )
    session.add(job)
    await session.flush()

    settings = get_settings()
    active = _provider(provider)
    started = await active.start(
        EscrowStart(
            reference=f"JOB-{job.id}",
            description=request.title,
            amount=request.amount,
            client=EscrowParty(request.client_name, request.client_email, request.client_phone),
            worker=EscrowParty(person.display_name if person else "", person.email if person else "", person.phone if person else None),
            webhook_url=settings.payscrow_webhook_url or None,
            return_url=request.return_url,
        )
    )
    escrow = EscrowTransaction(
        job_id=job.id,
        provider=started.provider,
        provider_reference=started.transaction_number,
        payment_link=started.payment_link,
        total_payable=started.total_payable,
        amount=request.amount,
        status=EscrowStatus.PENDING,
    )
    session.add(escrow)
    await session.flush()
    _audit(session, job, "escrow.opened", transaction_number=started.transaction_number)
    return job, escrow


# --- Webhooks ---------------------------------------------------------------


async def _find_by_webhook(session: AsyncSession, payload: dict) -> EscrowTransaction | None:
    number = payload.get("transactionNumber")
    if number:
        escrow = await session.scalar(
            select(EscrowTransaction).where(EscrowTransaction.provider_reference == number)
        )
        if escrow:
            return escrow

    # Fall back to our own reference, "JOB-{id}".
    reference = str(payload.get("externalReference") or "")
    if reference.startswith("JOB-"):
        try:
            return await latest_escrow(session, UUID(reference.removeprefix("JOB-")))
        except ValueError:
            return None
    return None


async def handle_webhook(session: AsyncSession, payload: dict, *, delivery_id: str) -> str:
    """Apply one Payscrow webhook. Retries of the same delivery are ignored.

    Returns what happened, for logs and tests.
    """

    operation = ProviderOperation(
        provider="payscrow",
        operation_type=str(payload.get("event") or "transaction.paid"),
        entity_type="escrow_transaction",
        entity_id=UUID(int=0),
        idempotency_key=f"payscrow:{delivery_id}",
        status=ProviderOperationStatus.PENDING,
        request_payload={key: value for key, value in payload.items() if key != "escrowCode"},
    )
    try:
        async with session.begin_nested():
            session.add(operation)
            await session.flush()
    except IntegrityError:
        return "duplicate"

    escrow = await _find_by_webhook(session, payload)
    if escrow is None:
        operation.status = ProviderOperationStatus.FAILED
        return "unknown transaction"
    operation.entity_id = escrow.id
    job = await session.get(Job, escrow.job_id)

    if payload.get("event") == "dispute.status_changed":
        outcome = await _apply_dispute_update(session, escrow, job, payload)
    else:
        outcome = _apply_payment(session, escrow, job, payload)

    operation.status = ProviderOperationStatus.SUCCEEDED
    return outcome


def _apply_payment(
    session: AsyncSession, escrow: EscrowTransaction, job: Job, payload: dict
) -> str:
    if str(payload.get("paymentStatus", "")).lower() != "paid":
        return "ignored"

    # The guide asks for the paid amount and currency to match the order; a
    # mismatch is recorded for an operator rather than treated as funded.
    expected = escrow.total_payable
    try:
        paid = Decimal(str(payload.get("amountPaid"))) if payload.get("amountPaid") is not None else None
    except (ArithmeticError, ValueError):
        paid = None
    currency = payload.get("currency")
    if (expected is not None and paid is not None and paid != expected) or (
        currency and currency != escrow.currency
    ):
        _audit(session, job, "escrow.payment_mismatch", amount_paid=str(paid), currency=currency)
        return "amount mismatch"

    escrow.provider_transaction_id = payload.get("transactionId") or escrow.provider_transaction_id
    code = str(payload.get("escrowCode") or "").strip()
    if ESCROW_CODE.match(code):
        escrow.escrow_code = code

    if escrow.status is EscrowStatus.PENDING:
        escrow.status = EscrowStatus.HELD
        escrow.funded_at = _now()
        if job.status is JobStatus.ACCEPTED:
            job.status = JobStatus.IN_PROGRESS
        _audit(session, job, "escrow.funded", code_received=escrow.escrow_code is not None)
    return "funded"


async def _apply_dispute_update(
    session: AsyncSession, escrow: EscrowTransaction, job: Job, payload: dict
) -> str:
    escrow.in_dispute = bool(payload.get("inDispute", True))
    escrow.dispute_stage = payload.get("disputeStage") or escrow.dispute_stage
    dispute = await session.scalar(
        select(Dispute).where(Dispute.job_id == job.id).order_by(Dispute.created_at.desc())
    )

    if payload.get("disputeStage") != "Resolved":
        if dispute and dispute.status is DisputeStatus.OPEN:
            dispute.status = DisputeStatus.UNDER_REVIEW
        _audit(session, job, "escrow.dispute_updated", stage=escrow.dispute_stage)
        return "dispute updated"

    resolution = payload.get("resolutionType")
    escrow.resolution_type = resolution
    escrow.in_dispute = False
    if dispute:
        dispute.status = DisputeStatus.RESOLVED
        dispute.resolved_at = _now()

    # Refund: the client gets the money back. Close: it goes to the worker as
    # agreed. Split: each gets a share, which Payscrow pays out itself.
    if resolution == "Refund":
        escrow.status = EscrowStatus.REFUNDED
        job.status = JobStatus.CANCELLED
    else:
        escrow.status = EscrowStatus.RELEASED
        escrow.released_at = _now()
        job.status = JobStatus.RELEASED
    _audit(session, job, "escrow.dispute_resolved", resolution=resolution)
    return f"dispute resolved: {resolution}"


# --- Worker actions ---------------------------------------------------------


async def worker_job(session: AsyncSession, user: User, job_id: UUID) -> tuple[Job, EscrowTransaction | None]:
    """A job, only if it belongs to this worker."""

    worker = await session.scalar(select(Worker).where(Worker.user_id == user.id))
    job = await session.get(Job, job_id)
    if worker is None or job is None or job.worker_id != worker.id:
        raise JobNotFoundError(f"No job with id {job_id}.")
    return job, await latest_escrow(session, job.id)


async def mark_complete(
    session: AsyncSession, user: User, job_id: UUID, *, now: datetime | None = None
) -> Job:
    """The worker says the work is done; the client's window to respond opens."""

    job, escrow = await worker_job(session, user, job_id)
    if escrow is None or escrow.status is not EscrowStatus.HELD or escrow.in_dispute:
        raise EscrowStateError("Payment must be held in escrow before the job can be completed.")
    if job.status is not JobStatus.IN_PROGRESS:
        raise EscrowStateError("This job is not in progress.")

    moment = now or _now()
    job.status = JobStatus.SUBMITTED
    job.completed_at = moment
    job.auto_release_at = moment + timedelta(hours=get_settings().escrow_auto_release_hours)
    _audit(session, job, "job.completed", actor=str(user.id))
    return job


async def report_issue(
    session: AsyncSession,
    user: User,
    job_id: UUID,
    *,
    reason: str,
    complaint: str,
    provider: EscrowProvider | None = None,
) -> Dispute:
    """The worker raises a problem; Payscrow holds the money until it rules."""

    job, escrow = await worker_job(session, user, job_id)
    if escrow is None or escrow.status is not EscrowStatus.HELD:
        raise EscrowStateError("Only money held in escrow can be disputed.")
    if escrow.in_dispute:
        raise EscrowStateError("This job is already under dispute.")

    text = f"{reason}. {complaint}".strip(" .") if complaint else reason
    text = text.ljust(COMPLAINT_MIN, ".")[:COMPLAINT_MAX]
    await _provider(provider).raise_dispute(
        escrow.provider_reference or "", requested_by="merchant", complaint=text
    )

    dispute = Dispute(job_id=job.id, opened_by_id=user.id, reason=text, status=DisputeStatus.OPEN)
    session.add(dispute)
    escrow.in_dispute = True
    escrow.dispute_stage = "NegotiationOpen"
    job.status = JobStatus.DISPUTED
    await session.flush()
    _audit(session, job, "escrow.dispute_raised", actor=str(user.id))
    return dispute


# --- Release ----------------------------------------------------------------


async def release(
    session: AsyncSession,
    job_id: UUID,
    *,
    by: str,
    code: str | None = None,
    provider: EscrowProvider | None = None,
    now: datetime | None = None,
) -> EscrowTransaction:
    """Release the held money to the worker by applying the escrow code.

    `code` is the one the client received from Payscrow; without it, the code
    from the paid webhook is used if Payscrow included one.
    """

    job = await session.get(Job, job_id)
    escrow = await latest_escrow(session, job_id) if job else None
    if job is None or escrow is None:
        raise JobNotFoundError(f"No job with id {job_id}.")
    if escrow.status is not EscrowStatus.HELD or escrow.in_dispute:
        raise EscrowStateError("There is no undisputed payment held for this job.")
    supplied = (code or "").strip()
    if supplied and not ESCROW_CODE.match(supplied):
        raise EscrowStateError("That does not look like an escrow code.")
    release_code = supplied or escrow.escrow_code
    if not release_code:
        raise EscrowCodeMissingError(
            "The client's escrow code is needed to release the funds. Payscrow sent "
            "it to the client when they paid."
        )
    if not escrow.provider_transaction_id:
        raise EscrowStateError("Payscrow has not confirmed this payment yet.")

    await _provider(provider).apply_code(escrow.provider_transaction_id, release_code)
    moment = now or _now()
    escrow.status = EscrowStatus.RELEASED
    escrow.released_at = moment
    job.status = JobStatus.RELEASED
    if job.completed_at is None:
        job.completed_at = moment
    _audit(session, job, "escrow.released", by=by)
    return escrow


async def release_due(
    session: AsyncSession,
    *,
    provider: EscrowProvider | None = None,
    now: datetime | None = None,
) -> list[UUID]:
    """Release every completed job whose client let the window pass.

    Called by the sweep, so it never raises: a job that cannot be released yet
    (no code, a provider error) is tried again on the next run.
    """

    moment = now or _now()
    due = (
        await session.scalars(
            select(Job).where(Job.status == JobStatus.SUBMITTED, Job.auto_release_at <= moment)
        )
    ).all()

    released: list[UUID] = []
    for job in due:
        try:
            async with session.begin_nested():
                await release(session, job.id, by="auto-release", provider=provider, now=moment)
            released.append(job.id)
        except (EscrowError, provider_module.EscrowProviderError):
            continue
    return released


def job_stage(job: Job, escrow: EscrowTransaction | None) -> str:
    """Where the job's money stands, in the terms the worker screens use."""

    if escrow is None or escrow.status is EscrowStatus.PENDING:
        return "awaiting_payment"
    if escrow.in_dispute or job.status is JobStatus.DISPUTED:
        return "disputed"
    if escrow.status is EscrowStatus.RELEASED:
        return "released"
    if escrow.status is EscrowStatus.REFUNDED:
        return "refunded"
    if job.status is JobStatus.SUBMITTED:
        return "awaiting_confirmation"
    return "held"
