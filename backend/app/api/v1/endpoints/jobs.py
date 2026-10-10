"""Purpose: Expose freelance jobs to their worker, their customer, and Payscrow.

Dependencies: FastAPI, SQLAlchemy async sessions, app.services.escrow.
Used by: the worker job screens (session), the customer's job page (the job
link's token, since customers have no account), and Payscrow's webhook
(signature).
"""

import json
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Request, UploadFile
from pydantic import Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.auth import current_user
from app.core.config import get_settings
from app.db.session import get_db_session
from app.models.domain import AuditEvent, EscrowTransaction, Job, User, Worker
from app.schemas.api import ApiModel
from app.services import document_store as document_store_module
from app.services import escrow as escrow_service
from app.services import insurance, job_notifications
from app.services.document_store import (
    DocumentStorageError,
    DocumentTooLargeError,
    UnsupportedDocumentError,
)
from app.services.escrow_provider import EscrowProviderError, verify_webhook
from app.services.trust_scoring.assessment import assess_worker

worker_router = APIRouter(prefix="/me/jobs", tags=["jobs"])
public_router = APIRouter(prefix="/public/jobs", tags=["jobs"])
webhook_router = APIRouter(prefix="/webhooks", tags=["jobs"])

#: Evidence files per report.
MAX_EVIDENCE_FILES = 5

#: Failures a report can run into, all mapped by _http_error.
REPORT_ERRORS = (
    escrow_service.EscrowError,
    EscrowProviderError,
    UnsupportedDocumentError,
    DocumentTooLargeError,
    DocumentStorageError,
)


# --- Shapes -----------------------------------------------------------------------


class JobLinkRequest(ApiModel):
    title: str = Field(min_length=1, max_length=200)
    address: str = Field(min_length=1, max_length=160)
    scheduled_at: datetime
    price: Decimal = Field(gt=0, max_digits=12, decimal_places=2)


class DisputeStep(ApiModel):
    stage: str
    at: datetime


class DisputeView(ApiModel):
    reference: str
    reason: str
    #: "customer", "worker", or "timeout".
    raised_by: str
    #: Payscrow's stage: NegotiationOpen, EvidenceCollection,
    #: AwaitingArbiterDecision, Resolved.
    stage: str | None = None
    resolution: str | None = None
    submitted_at: datetime
    history: list[DisputeStep] = Field(default_factory=list)


class JobView(ApiModel):
    """What the worker sees."""

    id: UUID
    title: str
    amount: Decimal
    address: str | None = None
    scheduled_at: datetime | None = None
    #: The link to send the customer.
    link: str
    #: awaiting_customer, awaiting_payment, held, awaiting_confirmation,
    #: disputed, released or refunded.
    stage: str
    created_at: datetime
    client_name: str | None = None
    client_email: str | None = None
    client_phone: str | None = None
    funded_at: datetime | None = None
    completed_at: datetime | None = None
    released_at: datetime | None = None
    transaction_number: str | None = None
    premium: Decimal | None = None
    cover_active: bool = False
    rating: int | None = None
    dispute: DisputeView | None = None


class WorkerCard(ApiModel):
    name: str
    role: str | None = None
    avatar_url: str | None = None
    band: str
    score: float | None = None


class PublicJobView(ApiModel):
    """What the customer sees on the job link."""

    title: str
    amount: Decimal
    #: Micro-insurance premium paid on top of the job.
    premium: Decimal
    address: str | None = None
    scheduled_at: datetime | None = None
    worker: WorkerCard
    stage: str
    created_at: datetime
    customer_name: str | None = None
    payment_link: str | None = None
    total_payable: Decimal | None = None
    funded_at: datetime | None = None
    completed_at: datetime | None = None
    released_at: datetime | None = None
    #: When the customer must release or report by, once the job is completed.
    confirm_by: datetime | None = None
    rating: int | None = None
    dispute: DisputeView | None = None


class PaymentRequest(ApiModel):
    name: str = Field(min_length=2, max_length=300)
    email: str = Field(min_length=3, max_length=320)
    #: Nigerian format, e.g. 08012345678 or +2348012345678.
    phone: str = Field(min_length=10, max_length=20)


class PaymentResponse(ApiModel):
    payment_link: str
    total_payable: Decimal


class ReleaseRequest(ApiModel):
    #: The escrow code Payscrow emailed the customer; passed on, never kept.
    code: str = Field(min_length=4, max_length=40)
    rating: int = Field(ge=1, le=5)


# --- Helpers ----------------------------------------------------------------------


def _http_error(error: Exception) -> HTTPException:
    if isinstance(error, escrow_service.JobNotFoundError):
        return HTTPException(status_code=404, detail=str(error))
    if isinstance(error, escrow_service.EscrowCodeMissingError):
        return HTTPException(status_code=409, detail=str(error))
    if isinstance(error, escrow_service.EscrowStateError):
        return HTTPException(status_code=409, detail=str(error))
    if isinstance(error, EscrowProviderError):
        return HTTPException(status_code=502, detail=f"Payscrow: {error}")
    if isinstance(error, (UnsupportedDocumentError, DocumentTooLargeError)):
        return HTTPException(status_code=422, detail=str(error))
    if isinstance(error, DocumentStorageError):
        return HTTPException(status_code=503, detail="We could not upload your evidence. Try again.")
    return HTTPException(status_code=400, detail=str(error))


async def _dispute_view(session: AsyncSession, job: Job, escrow: EscrowTransaction | None) -> DisputeView | None:
    dispute = await escrow_service.latest_dispute(session, job.id)
    if dispute is None:
        return None

    events = (
        await session.scalars(
            select(AuditEvent)
            .where(
                AuditEvent.entity_type == "job",
                AuditEvent.entity_id == job.id,
                AuditEvent.action.in_(
                    ("escrow.dispute_raised", "escrow.dispute_updated", "escrow.dispute_resolved")
                ),
            )
            .order_by(AuditEvent.created_at)
        )
    ).all()
    history: list[DisputeStep] = []
    for event in events:
        stage = {
            "escrow.dispute_raised": "NegotiationOpen",
            "escrow.dispute_resolved": "Resolved",
        }.get(event.action) or (event.event_metadata or {}).get("stage")
        if stage and (not history or history[-1].stage != stage):
            history.append(DisputeStep(stage=stage, at=event.created_at))

    return DisputeView(
        reference=f"D-{dispute.id.hex[:6].upper()}",
        reason=dispute.reason,
        raised_by=dispute.raised_by,
        stage=escrow.dispute_stage if escrow else None,
        resolution=escrow.resolution_type if escrow else None,
        submitted_at=dispute.created_at,
        history=history,
    )


async def _job_view(session: AsyncSession, job: Job, escrow: EscrowTransaction | None) -> JobView:
    paid = escrow is not None and escrow.funded_at is not None
    return JobView(
        id=job.id,
        title=job.title,
        amount=job.agreed_amount,
        address=job.location,
        scheduled_at=job.scheduled_at,
        link=job_notifications.job_page_url(job),
        stage=escrow_service.job_stage(job, escrow),
        created_at=job.created_at,
        # Customer details once they have paid (job flow: "customer info once paid").
        client_name=job.client_name if paid else None,
        client_email=job.client_email if paid else None,
        client_phone=job.client_phone if paid else None,
        funded_at=escrow.funded_at if escrow else None,
        completed_at=job.completed_at,
        released_at=escrow.released_at if escrow else None,
        transaction_number=escrow.provider_reference if escrow else None,
        premium=escrow.micro_premium if escrow else None,
        cover_active=escrow.cover_active if escrow else False,
        rating=job.rating,
        dispute=await _dispute_view(session, job, escrow),
    )


async def _store_evidence(files: list[UploadFile], job: Job) -> list[str]:
    references: list[str] = []
    for upload in [item for item in files if item and item.filename][:MAX_EVIDENCE_FILES]:
        stored = await document_store_module.default_document_store.store(
            filename=upload.filename,
            content=await upload.read(),
            prefix=f"dispute-evidence/{job.id}",
        )
        await upload.close()
        if stored.reference:
            references.append(stored.reference)
    return references


# --- Worker -----------------------------------------------------------------------


@worker_router.post("", response_model=JobView, status_code=201, summary="Create a job link")
async def create_job(
    payload: JobLinkRequest,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_db_session),
) -> JobView:
    try:
        job = await escrow_service.create_job_link(
            session,
            user,
            title=payload.title.strip(),
            address=payload.address.strip(),
            scheduled_at=payload.scheduled_at,
            price=payload.price,
        )
    except escrow_service.EscrowError as error:
        raise _http_error(error) from error
    await session.commit()
    return await _job_view(session, job, None)


@worker_router.get("", response_model=list[JobView], summary="The worker's jobs")
async def list_my_jobs(
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[JobView]:
    worker = await session.scalar(select(Worker).where(Worker.user_id == user.id))
    if worker is None:
        raise HTTPException(status_code=404, detail="This account has no worker profile.")
    jobs = (
        await session.scalars(
            select(Job).where(Job.worker_id == worker.id).order_by(Job.created_at.desc())
        )
    ).all()
    return [await _job_view(session, job, await escrow_service.latest_escrow(session, job.id)) for job in jobs]


@worker_router.get("/{job_id}", response_model=JobView, summary="One of the worker's jobs")
async def get_my_job(
    job_id: UUID,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_db_session),
) -> JobView:
    try:
        job, escrow = await escrow_service.worker_job(session, user, job_id)
    except escrow_service.EscrowError as error:
        raise _http_error(error) from error
    return await _job_view(session, job, escrow)


@worker_router.post("/{job_id}/complete", response_model=JobView, summary="Mark the job completed")
async def complete_my_job(
    job_id: UUID,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_db_session),
) -> JobView:
    try:
        job = await escrow_service.mark_complete(session, user, job_id)
    except escrow_service.EscrowError as error:
        raise _http_error(error) from error
    await session.commit()
    return await _job_view(session, job, await escrow_service.latest_escrow(session, job.id))


@worker_router.post("/{job_id}/issue", response_model=JobView, summary="Report an issue")
async def report_my_issue(
    job_id: UUID,
    reason: str = Form(..., min_length=3, max_length=120),
    complaint: str = Form("", max_length=900),
    evidence: list[UploadFile] = File(default_factory=list),
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_db_session),
) -> JobView:
    try:
        job, _ = await escrow_service.worker_job(session, user, job_id)
        references = await _store_evidence(evidence, job)
        await escrow_service.report_issue_by_worker(
            session, user, job_id, reason=reason, complaint=complaint, evidence=references
        )
    except REPORT_ERRORS as error:
        raise _http_error(error) from error
    await session.commit()
    job = await session.get(Job, job_id)
    return await _job_view(session, job, await escrow_service.latest_escrow(session, job_id))


# --- Customer (by job link) -----------------------------------------------------------


async def _public_view(session: AsyncSession, job: Job, escrow: EscrowTransaction | None) -> PublicJobView:
    worker = await session.get(Worker, job.worker_id)
    person = await session.get(User, worker.user_id)
    assessment = await assess_worker(session, worker.id, "generic")
    window = get_settings().escrow_confirmation_window_hours

    return PublicJobView(
        title=job.title,
        amount=job.agreed_amount,
        premium=escrow.micro_premium if escrow else insurance.premium_for(job.agreed_amount),
        address=job.location,
        scheduled_at=job.scheduled_at,
        worker=WorkerCard(
            name=person.display_name,
            role=worker.role,
            avatar_url=worker.avatar_url,
            band=assessment.band,
            score=float(assessment.score) if assessment.score is not None else None,
        ),
        stage=escrow_service.job_stage(job, escrow),
        created_at=job.created_at,
        customer_name=job.client_name,
        payment_link=escrow.payment_link if escrow and escrow.funded_at is None else None,
        total_payable=escrow.total_payable if escrow else None,
        funded_at=escrow.funded_at if escrow else None,
        completed_at=job.completed_at,
        released_at=escrow.released_at if escrow else None,
        confirm_by=job.completed_at + timedelta(hours=window) if job.completed_at else None,
        rating=job.rating,
        dispute=await _dispute_view(session, job, escrow),
    )


@public_router.get("/{token}", response_model=PublicJobView, summary="The job, for its customer")
async def get_public_job(token: str, session: AsyncSession = Depends(get_db_session)) -> PublicJobView:
    try:
        job, escrow = await escrow_service.job_by_token(session, token)
    except escrow_service.EscrowError as error:
        raise _http_error(error) from error
    view = await _public_view(session, job, escrow)
    # Assessing stores (or reuses) the worker's assessment.
    await session.commit()
    return view


@public_router.post("/{token}/payment", response_model=PaymentResponse, summary="Pay into escrow")
async def start_payment(
    token: str, payload: PaymentRequest, session: AsyncSession = Depends(get_db_session)
) -> PaymentResponse:
    base = get_settings().frontend_base_url.rstrip("/")
    try:
        escrow = await escrow_service.start_payment(
            session,
            token,
            name=payload.name,
            email=payload.email,
            phone=payload.phone,
            # Payscrow sends the customer back to their job page after paying.
            return_url=f"{base}/j/{token}",
        )
    except (escrow_service.EscrowError, EscrowProviderError) as error:
        raise _http_error(error) from error
    await session.commit()
    return PaymentResponse(payment_link=escrow.payment_link or "", total_payable=escrow.total_payable or Decimal(0))


@public_router.post("/{token}/release", response_model=PublicJobView, summary="Release with the code and rate")
async def release_payment(
    token: str, payload: ReleaseRequest, session: AsyncSession = Depends(get_db_session)
) -> PublicJobView:
    try:
        await escrow_service.release_by_customer(session, token, code=payload.code, rating=payload.rating)
    except (escrow_service.EscrowError, EscrowProviderError) as error:
        raise _http_error(error) from error
    await session.commit()
    job, escrow = await escrow_service.job_by_token(session, token)
    view = await _public_view(session, job, escrow)
    await session.commit()
    return view


@public_router.post("/{token}/issue", response_model=PublicJobView, summary="Report a problem")
async def report_customer_issue(
    token: str,
    reason: str = Form(..., min_length=3, max_length=120),
    complaint: str = Form("", max_length=900),
    evidence: list[UploadFile] = File(default_factory=list),
    session: AsyncSession = Depends(get_db_session),
) -> PublicJobView:
    try:
        job, _ = await escrow_service.job_by_token(session, token)
        references = await _store_evidence(evidence, job)
        await escrow_service.report_issue_by_customer(
            session, token, reason=reason, complaint=complaint, evidence=references
        )
    except REPORT_ERRORS as error:
        raise _http_error(error) from error
    await session.commit()
    job, escrow = await escrow_service.job_by_token(session, token)
    view = await _public_view(session, job, escrow)
    await session.commit()
    return view


# --- Payscrow -----------------------------------------------------------------------


@webhook_router.post("/payscrow", summary="Payscrow transaction and dispute updates")
async def payscrow_webhook(
    request: Request,
    signature: str | None = Header(default=None, alias="X-PayScrow-Signature"),
    timestamp: str | None = Header(default=None, alias="X-PayScrow-Timestamp"),
    delivery_id: str | None = Header(default=None, alias="X-PayScrow-Delivery-Id"),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, str]:
    body = await request.body()
    if not verify_webhook(get_settings().payscrow_webhook_secret, body, signature, timestamp):
        raise HTTPException(status_code=401, detail="Invalid webhook signature.")

    try:
        payload = json.loads(body)
    except ValueError as error:
        raise HTTPException(status_code=400, detail="Malformed webhook body.") from error

    # Dispute events carry their own stable id; payment events rely on the header.
    key = delivery_id or str(payload.get("eventId") or "")
    if not key:
        raise HTTPException(status_code=400, detail="Missing delivery id.")

    outcome = await escrow_service.handle_webhook(session, payload, delivery_id=key)
    await session.commit()
    # A 2xx stops Payscrow retrying; an unknown transaction will not get better.
    return {"status": outcome}
