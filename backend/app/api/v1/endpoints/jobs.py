"""Purpose: Expose escrow-protected jobs to platforms, workers and Payscrow.

Dependencies: FastAPI, SQLAlchemy async sessions, app.services.escrow.
Used by: platforms opening jobs and confirming them for clients (API key),
the worker jobs screens (session), and Payscrow's webhook (signature).
"""

import json
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.auth import current_user
from app.core.config import get_settings
from app.core.platform_auth import require_platform_api_key
from app.db.session import get_db_session
from app.models.domain import Dispute, EscrowTransaction, Job, User, Worker
from app.schemas.api import ApiModel
from app.services import escrow as escrow_service
from app.services.escrow_provider import EscrowProviderError, verify_webhook

platform_router = APIRouter(prefix="/jobs", tags=["escrow"])
worker_router = APIRouter(prefix="/me/jobs", tags=["escrow"])
webhook_router = APIRouter(prefix="/webhooks", tags=["escrow"])


class JobDetailItem(ApiModel):
    label: str = Field(min_length=1, max_length=60)
    value: str = Field(min_length=1, max_length=120)


class JobCreateRequest(ApiModel):
    worker_id: UUID
    title: str = Field(min_length=1, max_length=200)
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    client_name: str = Field(min_length=2, max_length=300)
    client_email: str = Field(min_length=3, max_length=320)
    #: Nigerian format, e.g. 08012345678; Payscrow requires it for the client.
    client_phone: str = Field(min_length=10, max_length=40)
    location: str | None = Field(default=None, max_length=160)
    details: list[JobDetailItem] = Field(default_factory=list, max_length=12)
    #: Where Payscrow sends the client after paying.
    return_url: str | None = None


class JobCreateResponse(ApiModel):
    job_id: UUID
    transaction_number: str
    payment_link: str
    total_payable: Decimal


class ClientConfirmRequest(ApiModel):
    #: Kept for the record; the platform vouches that the client confirmed.
    note: str | None = Field(default=None, max_length=500)


class EscrowView(ApiModel):
    transaction_number: str | None = None
    payment_link: str | None = None
    total_payable: Decimal | None = None
    funded_at: datetime | None = None
    released_at: datetime | None = None
    cover_active: bool = False
    #: Whether we can release without asking the worker for the code.
    code_on_file: bool = False
    dispute_stage: str | None = None
    resolution_type: str | None = None


class DisputeView(ApiModel):
    id: UUID
    reference: str
    reason: str
    submitted_at: datetime


class JobView(ApiModel):
    id: UUID
    title: str
    amount: Decimal
    client_name: str | None = None
    location: str | None = None
    details: list[dict[str, str]] = Field(default_factory=list)
    #: awaiting_payment, held, awaiting_confirmation, disputed, released or refunded.
    stage: str
    assigned_at: datetime
    completed_at: datetime | None = None
    auto_release_at: datetime | None = None
    escrow: EscrowView | None = None
    dispute: DisputeView | None = None


class IssueRequest(ApiModel):
    reason: str = Field(min_length=3, max_length=120)
    complaint: str = Field(default="", max_length=900)


class EscrowCodeRequest(ApiModel):
    code: str = Field(min_length=4, max_length=40)


def _http_error(error: Exception) -> HTTPException:
    if isinstance(error, escrow_service.JobNotFoundError):
        return HTTPException(status_code=404, detail=str(error))
    if isinstance(error, escrow_service.EscrowCodeMissingError):
        return HTTPException(status_code=409, detail=str(error))
    if isinstance(error, escrow_service.EscrowStateError):
        return HTTPException(status_code=409, detail=str(error))
    if isinstance(error, EscrowProviderError):
        return HTTPException(status_code=502, detail=f"Payscrow: {error}")
    return HTTPException(status_code=400, detail=str(error))


async def _view(session: AsyncSession, job: Job, escrow: EscrowTransaction | None) -> JobView:
    dispute = await session.scalar(
        select(Dispute).where(Dispute.job_id == job.id).order_by(Dispute.created_at.desc())
    )
    return JobView(
        id=job.id,
        title=job.title,
        amount=job.agreed_amount,
        client_name=job.client_name,
        location=job.location,
        details=job.details or [],
        stage=escrow_service.job_stage(job, escrow),
        assigned_at=job.created_at,
        completed_at=job.completed_at,
        auto_release_at=job.auto_release_at,
        escrow=EscrowView(
            transaction_number=escrow.provider_reference,
            payment_link=escrow.payment_link,
            total_payable=escrow.total_payable,
            funded_at=escrow.funded_at,
            released_at=escrow.released_at,
            cover_active=escrow.cover_active,
            code_on_file=bool(escrow.escrow_code),
            dispute_stage=escrow.dispute_stage,
            resolution_type=escrow.resolution_type,
        )
        if escrow
        else None,
        dispute=DisputeView(
            id=dispute.id,
            reference=f"D-{dispute.id.hex[:4].upper()}",
            reason=dispute.reason,
            submitted_at=dispute.created_at,
        )
        if dispute
        else None,
    )


# --- Platforms ----------------------------------------------------------------


@platform_router.post(
    "",
    response_model=JobCreateResponse,
    status_code=201,
    summary="Open a job and its escrow",
)
async def create_job(
    payload: JobCreateRequest,
    _: None = Depends(require_platform_api_key),
    session: AsyncSession = Depends(get_db_session),
) -> JobCreateResponse:
    try:
        job, escrow = await escrow_service.open_job(
            session,
            escrow_service.JobRequest(
                worker_id=payload.worker_id,
                title=payload.title,
                amount=payload.amount,
                client_name=payload.client_name,
                client_email=payload.client_email,
                client_phone=payload.client_phone,
                location=payload.location,
                details=[item.model_dump() for item in payload.details],
                return_url=payload.return_url,
            ),
        )
    except (escrow_service.EscrowError, EscrowProviderError) as error:
        raise _http_error(error) from error

    await session.commit()
    return JobCreateResponse(
        job_id=job.id,
        transaction_number=escrow.provider_reference or "",
        payment_link=escrow.payment_link or "",
        total_payable=escrow.total_payable or job.agreed_amount,
    )


@platform_router.get("/{job_id}", response_model=JobView, summary="Where a job's money stands")
async def get_job(
    job_id: UUID,
    _: None = Depends(require_platform_api_key),
    session: AsyncSession = Depends(get_db_session),
) -> JobView:
    job = await session.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"No job with id {job_id}.")
    return await _view(session, job, await escrow_service.latest_escrow(session, job.id))


@platform_router.post(
    "/{job_id}/client-confirmation",
    response_model=JobView,
    summary="The client confirms the work; release the funds",
)
async def confirm_for_client(
    job_id: UUID,
    payload: ClientConfirmRequest | None = None,
    _: None = Depends(require_platform_api_key),
    session: AsyncSession = Depends(get_db_session),
) -> JobView:
    """No client screen exists yet; the platform calls this on the client's behalf."""

    try:
        escrow = await escrow_service.release(session, job_id, by="client")
    except (escrow_service.EscrowError, EscrowProviderError) as error:
        raise _http_error(error) from error

    await session.commit()
    job = await session.get(Job, job_id)
    return await _view(session, job, escrow)


# --- Payscrow -------------------------------------------------------------------


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


# --- Workers --------------------------------------------------------------------


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
    return [await _view(session, job, await escrow_service.latest_escrow(session, job.id)) for job in jobs]


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
    return await _view(session, job, escrow)


@worker_router.post("/{job_id}/complete", response_model=JobView, summary="Mark the job complete")
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
    return await _view(session, job, await escrow_service.latest_escrow(session, job.id))


@worker_router.post("/{job_id}/issue", response_model=JobView, summary="Report an issue")
async def report_my_issue(
    job_id: UUID,
    payload: IssueRequest,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_db_session),
) -> JobView:
    try:
        await escrow_service.report_issue(
            session, user, job_id, reason=payload.reason, complaint=payload.complaint
        )
    except (escrow_service.EscrowError, EscrowProviderError) as error:
        raise _http_error(error) from error

    await session.commit()
    job = await session.get(Job, job_id)
    return await _view(session, job, await escrow_service.latest_escrow(session, job_id))


@worker_router.post(
    "/{job_id}/escrow-code",
    status_code=204,
    summary="Pass on the escrow code Payscrow emailed",
)
async def submit_escrow_code(
    job_id: UUID,
    payload: EscrowCodeRequest,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_db_session),
) -> None:
    try:
        await escrow_service.record_escrow_code(session, user, job_id, payload.code)
    except escrow_service.EscrowError as error:
        raise _http_error(error) from error
    await session.commit()
