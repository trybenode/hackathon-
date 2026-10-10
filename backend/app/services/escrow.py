"""Purpose: Run a freelance job's money through Payscrow escrow, from link to release.

Dependencies: SQLAlchemy async sessions, app.models.domain, the escrow provider
seam (Payscrow, or the local stand-in), insurance and job notifications.
Used by: the worker jobs, customer job page and Payscrow webhook endpoints,
and the background sweep.

The flow (Freelance Worker <-> Customer Job Flow, Oct 2026):
  1. link      worker creates the job (title, address, date, price) and shares
               its link. Job Draft; no money yet.
  2-3. pay     the customer opens the link (no account), enters name, email and
               phone, and is sent to Payscrow. Job Accepted, escrow Pending.
  4. held      Payscrow's signed webhook confirms payment. Job In Progress,
               escrow Held, cover active; Payscrow emails the code to the customer.
  5. complete  the worker marks it done; the customer is emailed and has
               ESCROW_CONFIRMATION_WINDOW_HOURS to act.
  6-7. release the customer enters the code and a 1-5 star rating. We apply the
               code; the job closes and is recorded as a verified outcome, so
               the rating feeds the worker's trust score.
  dispute      either party reports a problem before release, or the window
               passes without a code. Payscrow rules (Refund, Split, Close).

Money only ever moves on the customer's code or Payscrow's ruling. Codes are
passed to Payscrow and never stored.
"""

from __future__ import annotations

import hashlib
import re
import secrets
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
    NormalizedOutcome,
    Organization,
    OrganizationType,
    OutcomeSource,
    OutcomeStatus,
    ProviderOperation,
    ProviderOperationStatus,
    RawOutcome,
    User,
    Worker,
)
from app.services import escrow_provider as provider_module
from app.services import insurance, job_notifications
from app.services import worker_onboarding as onboarding
from app.services.escrow_provider import EscrowParty, EscrowProvider, EscrowStart

#: Payscrow's escrow code is 10 alphanumerics; this rejects obvious typos
#: before we ask Payscrow.
ESCROW_CODE = re.compile(r"^[A-Za-z0-9]{6,20}$")

#: Payscrow's complaint length limits.
COMPLAINT_MIN, COMPLAINT_MAX = 10, 1000

#: Where completed jobs are recorded as outcomes for the trust score.
OUTCOME_SOURCE = "credly-jobs"


class EscrowError(Exception):
    """Base class for escrow failures."""


class JobNotFoundError(EscrowError):
    """No such job, or not this worker's."""


class EscrowStateError(EscrowError):
    """The job's money is not in a state that allows this."""


class EscrowCodeMissingError(EscrowError):
    """Releasing needs the customer's escrow code."""


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
    """Freelance jobs hang off one placeholder organization: customers have no
    account of their own."""

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


async def latest_dispute(session: AsyncSession, job_id: UUID) -> Dispute | None:
    return await session.scalar(
        select(Dispute).where(Dispute.job_id == job_id).order_by(Dispute.created_at.desc())
    )


async def _worker_person(session: AsyncSession, job: Job) -> User | None:
    worker = await session.get(Worker, job.worker_id)
    return await session.get(User, worker.user_id) if worker else None


# --- 1. The worker creates the job link ---------------------------------------


async def create_job_link(
    session: AsyncSession,
    user: User,
    *,
    title: str,
    address: str,
    scheduled_at: datetime,
    price: Decimal,
) -> Job:
    """A job waiting for its customer; the link carries its secret token."""

    worker = await session.scalar(select(Worker).where(Worker.user_id == user.id))
    if worker is None:
        raise JobNotFoundError("This account has no worker profile.")
    if not await onboarding.has_active_guarantor(session, worker):
        raise EscrowStateError("Job creation opens once your guarantor is active.")
    # Payscrow requires the merchant's phone, whatever its docs say; better to
    # say so now than when the customer tries to pay.
    if not (user.phone or "").strip():
        raise EscrowStateError(
            "Add a phone number to your profile before creating a job: Payscrow needs it."
        )

    job = Job(
        worker_id=worker.id,
        organization_id=(await _client_organization(session)).id,
        job_type=JobType.INDEPENDENT,
        status=JobStatus.DRAFT,
        title=title,
        agreed_amount=price,
        location=address,
        scheduled_at=scheduled_at,
        link_token=secrets.token_urlsafe(16),
    )
    session.add(job)
    await session.flush()
    _audit(session, job, "job.link_created", actor=str(user.id))
    return job


async def job_by_token(session: AsyncSession, token: str) -> tuple[Job, EscrowTransaction | None]:
    job = await session.scalar(select(Job).where(Job.link_token == token))
    if job is None:
        raise JobNotFoundError("This job link is not valid.")
    return job, await latest_escrow(session, job.id)


# --- 2-3. The customer pays into escrow -----------------------------------------


async def start_payment(
    session: AsyncSession,
    token: str,
    *,
    name: str,
    email: str,
    phone: str,
    return_url: str | None = None,
    provider: EscrowProvider | None = None,
) -> EscrowTransaction:
    """Open the escrow with the customer's details; they pay on Payscrow.

    Asking again before paying returns the same payment link rather than a
    second payable order (Payscrow's guide, step 5).
    """

    job, escrow = await job_by_token(session, token)
    if escrow is not None:
        if escrow.status is EscrowStatus.PENDING:
            return escrow
        raise EscrowStateError("This job has already been paid for.")

    person = await _worker_person(session, job)
    if person is None:
        raise JobNotFoundError("This job's worker no longer exists.")
    if email.strip().casefold() == person.email.casefold():
        raise EscrowStateError("Use your own email: it must differ from the worker's.")

    job.client_name = name.strip()
    job.client_email = email.strip()
    job.client_phone = phone.strip()

    premium = insurance.premium_for(job.agreed_amount)
    started = await _provider(provider).start(
        EscrowStart(
            reference=f"JOB-{job.id}",
            description=job.title,
            amount=job.agreed_amount,
            client=EscrowParty(job.client_name, job.client_email, job.client_phone),
            worker=EscrowParty(person.display_name, person.email, person.phone),
            webhook_url=get_settings().payscrow_webhook_endpoint or None,
            return_url=return_url,
            premium=premium,
        )
    )
    escrow = EscrowTransaction(
        job_id=job.id,
        provider=started.provider,
        provider_reference=started.transaction_number,
        payment_link=started.payment_link,
        total_payable=started.total_payable,
        amount=job.agreed_amount,
        micro_premium=premium,
        status=EscrowStatus.PENDING,
    )
    session.add(escrow)
    job.status = JobStatus.ACCEPTED
    # Cover is quoted now and starts only once the premium is paid.
    insurance.quote(session, job.id, job.agreed_amount, premium)
    await session.flush()
    _audit(session, job, "escrow.opened", transaction_number=started.transaction_number)
    return escrow


# --- 4. Payscrow's webhooks -------------------------------------------------------


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
        outcome = await _apply_payment(session, escrow, job, payload)

    operation.status = ProviderOperationStatus.SUCCEEDED
    return outcome


async def _apply_payment(
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

    # Any escrowCode in the payload is ignored: releasing is the customer's
    # call, made by giving us their code.
    escrow.provider_transaction_id = payload.get("transactionId") or escrow.provider_transaction_id
    await _mark_funded(session, escrow, job, via="webhook")
    return "funded"


async def _mark_funded(session: AsyncSession, escrow: EscrowTransaction, job: Job, *, via: str) -> None:
    """The money is in escrow: the job starts. Safe to call more than once."""

    if escrow.status is not EscrowStatus.PENDING:
        return
    escrow.status = EscrowStatus.HELD
    escrow.funded_at = _now()
    if job.status is JobStatus.ACCEPTED:
        job.status = JobStatus.IN_PROGRESS
    _audit(session, job, "escrow.funded", via=via)
    # The payment included the premium: no premium, no cover, so only now.
    if await insurance.activate(session, escrow):
        _audit(session, job, "insurance.activated")
    person = await _worker_person(session, job)
    if person:
        await job_notifications.payment_received(job, person.email)


async def sync_payment(
    session: AsyncSession,
    job: Job,
    escrow: EscrowTransaction | None,
    *,
    provider: EscrowProvider | None = None,
) -> bool:
    """Ask Payscrow whether a still-pending payment has landed.

    Payscrow's guide (step 8): if notifications go missing, read the status.
    It confirms the money is held, so the job can start; it does not carry the
    transaction GUID, so releasing still waits for the paid webhook. Never
    raises: Payscrow being unreachable just means "not yet".
    """

    if escrow is None or escrow.status is not EscrowStatus.PENDING or not escrow.provider_reference:
        return False
    try:
        state = await _provider(provider).status(escrow.provider_reference)
    except provider_module.EscrowProviderError:
        return False
    if not state.in_escrow:
        return False
    await _mark_funded(session, escrow, job, via="status")
    return True


async def sync_pending_payments(session: AsyncSession, *, provider: EscrowProvider | None = None) -> list[UUID]:
    """The sweep's safety net for paid webhooks that never arrived."""

    pending = (
        await session.scalars(
            select(EscrowTransaction).where(
                EscrowTransaction.status == EscrowStatus.PENDING,
                EscrowTransaction.created_at >= _now() - timedelta(days=7),
            )
        )
    ).all()
    synced: list[UUID] = []
    for escrow in pending:
        job = await session.get(Job, escrow.job_id)
        if await sync_payment(session, job, escrow, provider=provider):
            synced.append(job.id)
    return synced


async def _apply_dispute_update(
    session: AsyncSession, escrow: EscrowTransaction, job: Job, payload: dict
) -> str:
    escrow.in_dispute = bool(payload.get("inDispute", True))
    escrow.dispute_stage = payload.get("disputeStage") or escrow.dispute_stage
    dispute = await latest_dispute(session, job.id)

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

    # Refund: the customer gets the money back. Close: it goes to the worker as
    # agreed. Split: each gets a share, which Payscrow pays out itself.
    if resolution == "Refund":
        escrow.status = EscrowStatus.REFUNDED
        job.status = JobStatus.CANCELLED
    else:
        escrow.status = EscrowStatus.RELEASED
        escrow.released_at = _now()
        job.status = JobStatus.RELEASED
    # A refund means the protected flow was abandoned: the cover is voided.
    await insurance.end(session, escrow, voided=resolution == "Refund")
    # The outcome affects the worker's score: a refund or split upholds the
    # complaint; a close dismisses it.
    await _record_outcome(
        session,
        job,
        status=OutcomeStatus.DISPUTED if resolution == "Refund" else OutcomeStatus.COMPLETED,
        dispute_resolution="dismissed" if resolution == "Close" else "upheld",
    )
    _audit(session, job, "escrow.dispute_resolved", resolution=resolution)
    return f"dispute resolved: {resolution}"


# --- 5. The worker marks the job complete ---------------------------------------


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
    """The worker says the work is done; the customer is told and the window opens."""

    job, escrow = await worker_job(session, user, job_id)
    if escrow is None or escrow.status is not EscrowStatus.HELD or escrow.in_dispute:
        raise EscrowStateError("Payment must be held in escrow before the job can be completed.")
    if job.status is not JobStatus.IN_PROGRESS:
        raise EscrowStateError("This job is not in progress.")

    job.status = JobStatus.SUBMITTED
    job.completed_at = now or _now()
    _audit(session, job, "job.completed", actor=str(user.id))
    await job_notifications.job_completed(
        job, user.display_name, get_settings().escrow_confirmation_window_hours
    )
    return job


# --- Disputes -----------------------------------------------------------------------


async def _open_dispute(
    session: AsyncSession,
    job: Job,
    escrow: EscrowTransaction | None,
    *,
    raised_by: str,
    requested_by: str,
    reason: str,
    complaint: str,
    opened_by: User | None,
    evidence: list[str] | None = None,
    provider: EscrowProvider | None = None,
) -> Dispute:
    if escrow is None or escrow.status is not EscrowStatus.HELD:
        raise EscrowStateError("Only money held in escrow can be disputed.")
    if escrow.in_dispute:
        raise EscrowStateError("This job is already under dispute.")

    text = f"{reason}. {complaint}".strip(" .") if complaint else reason
    text = text.ljust(COMPLAINT_MIN, ".")[:COMPLAINT_MAX]
    await _provider(provider).raise_dispute(
        escrow.provider_reference or "", requested_by=requested_by, complaint=text
    )

    dispute = Dispute(
        job_id=job.id,
        opened_by_id=opened_by.id if opened_by else None,
        raised_by=raised_by,
        reason=reason,
        status=DisputeStatus.OPEN,
        evidence_urls=evidence or [],
    )
    session.add(dispute)
    escrow.in_dispute = True
    escrow.dispute_stage = "NegotiationOpen"
    job.status = JobStatus.DISPUTED
    await session.flush()
    _audit(session, job, "escrow.dispute_raised", raised_by=raised_by)

    person = await _worker_person(session, job)
    await job_notifications.dispute_opened(job, person.email if person else "", raised_by, reason)
    return dispute


async def report_issue_by_worker(
    session: AsyncSession,
    user: User,
    job_id: UUID,
    *,
    reason: str,
    complaint: str,
    evidence: list[str] | None = None,
    provider: EscrowProvider | None = None,
) -> Dispute:
    job, escrow = await worker_job(session, user, job_id)
    return await _open_dispute(
        session, job, escrow, raised_by="worker", requested_by="merchant",
        reason=reason, complaint=complaint, opened_by=user, evidence=evidence, provider=provider,
    )


async def report_issue_by_customer(
    session: AsyncSession,
    token: str,
    *,
    reason: str,
    complaint: str,
    evidence: list[str] | None = None,
    provider: EscrowProvider | None = None,
) -> Dispute:
    job, escrow = await job_by_token(session, token)
    return await _open_dispute(
        session, job, escrow, raised_by="customer", requested_by="customer",
        reason=reason, complaint=complaint, opened_by=None, evidence=evidence, provider=provider,
    )


async def dispute_overdue_confirmations(
    session: AsyncSession,
    *,
    provider: EscrowProvider | None = None,
    now: datetime | None = None,
) -> list[UUID]:
    """Open a dispute for every completed job the customer left unconfirmed.

    Called by the sweep. The worker is owed, so it is raised as the merchant's
    complaint. A job whose dispute cannot be raised yet is tried next run.
    """

    window = timedelta(hours=get_settings().escrow_confirmation_window_hours)
    cutoff = (now or _now()) - window
    due = (
        await session.scalars(
            select(Job).where(Job.status == JobStatus.SUBMITTED, Job.completed_at <= cutoff)
        )
    ).all()

    opened: list[UUID] = []
    for job in due:
        escrow = await latest_escrow(session, job.id)
        hours = window.total_seconds() // 3600
        try:
            async with session.begin_nested():
                await _open_dispute(
                    session, job, escrow, raised_by="timeout", requested_by="merchant",
                    reason="Customer did not confirm",
                    complaint=f"The job was marked completed and the customer did not release "
                    f"payment or report a problem within {hours:.0f} hours.",
                    opened_by=None, provider=provider,
                )
            opened.append(job.id)
        except (EscrowError, provider_module.EscrowProviderError):
            continue
    return opened


# --- 6-7. The customer releases with their code and a rating -------------------------


async def release_by_customer(
    session: AsyncSession,
    token: str,
    *,
    code: str,
    rating: int,
    provider: EscrowProvider | None = None,
    now: datetime | None = None,
) -> EscrowTransaction:
    """Release the held money to the worker, and keep the customer's rating.

    One step, because both feed the trust score. The code is passed straight
    to Payscrow and not kept.
    """

    job, escrow = await job_by_token(session, token)
    if escrow is None or escrow.status is not EscrowStatus.HELD or escrow.in_dispute:
        raise EscrowStateError("There is no undisputed payment held for this job.")
    if not 1 <= rating <= 5:
        raise EscrowStateError("Rate the job from 1 to 5 stars to release the payment.")
    release_code = (code or "").strip()
    if not release_code:
        raise EscrowCodeMissingError(
            "Enter the escrow code Payscrow emailed you when you paid."
        )
    if not ESCROW_CODE.match(release_code):
        raise EscrowStateError("That does not look like an escrow code.")
    if not escrow.provider_transaction_id:
        # Only Payscrow's paid webhook carries the ID that releasing needs.
        raise EscrowStateError(
            "Payscrow's payment confirmation has not reached us yet, so the payment "
            "cannot be released. Try again in a few minutes."
        )

    await _provider(provider).apply_code(escrow.provider_transaction_id, release_code)
    moment = now or _now()
    escrow.status = EscrowStatus.RELEASED
    escrow.released_at = moment
    job.status = JobStatus.RELEASED
    job.rating = rating
    if job.completed_at is None:
        job.completed_at = moment
    await insurance.end(session, escrow, voided=False)
    await _record_outcome(session, job, status=OutcomeStatus.COMPLETED, rating=rating, now=moment)
    _audit(session, job, "escrow.released", rating=rating)

    person = await _worker_person(session, job)
    if person:
        await job_notifications.payment_released(job, person.email)
    return escrow


# --- 8. Settled jobs feed the trust score -------------------------------------------


async def _record_outcome(
    session: AsyncSession,
    job: Job,
    *,
    status: OutcomeStatus,
    rating: int | None = None,
    dispute_resolution: str | None = None,
    now: datetime | None = None,
) -> None:
    """Record a settled job as a verified outcome on the worker's history.

    The escrow is the evidence: Payscrow held the money and released it on the
    customer's code, or ruled on a dispute. assess_worker() and the portable
    record read these.
    """

    source = await session.scalar(select(OutcomeSource).where(OutcomeSource.name == OUTCOME_SOURCE))
    if source is None:
        source = OutcomeSource(name=OUTCOME_SOURCE, normalization_version="1")
        session.add(source)
        await session.flush()

    key = f"job-{job.id}"
    if await session.scalar(
        select(RawOutcome).where(RawOutcome.source_id == source.id, RawOutcome.external_outcome_id == key)
    ):
        return

    payload = {"job_id": str(job.id), "status": status.value, "rating": rating}
    raw = RawOutcome(
        source_id=source.id,
        external_outcome_id=key,
        payload=payload,
        payload_checksum=hashlib.sha256(repr(sorted(payload.items())).encode()).hexdigest(),
    )
    session.add(raw)
    await session.flush()
    session.add(
        NormalizedOutcome(
            worker_id=job.worker_id,
            job_id=job.id,
            raw_outcome_id=raw.id,
            outcome_key=key,
            status=status,
            occurred_at=now or _now(),
            rating=Decimal(rating) if rating else None,
            amount=job.agreed_amount,
            completion_confirmed=rating is not None,
            normalization_version="1",
            dispute_resolution=dispute_resolution,
            # Pseudonymous: lets repeat-hire counting work without the email.
            client_id=hashlib.sha256((job.client_email or "").casefold().encode()).hexdigest()[:16]
            if job.client_email
            else None,
            source_platform="native",
            import_method="native",
            verified=True,
            quality_flags=[],
        )
    )


def job_stage(job: Job, escrow: EscrowTransaction | None) -> str:
    """Where the job stands, in the terms both screens use."""

    if escrow is None:
        return "awaiting_customer"
    if escrow.status is EscrowStatus.PENDING:
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
