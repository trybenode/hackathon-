"""Purpose: Expose the developer dashboard, verification steps and credentials.

Dependencies: FastAPI, SQLAlchemy async sessions, app.services.developers.
Used by: the developer screens (dashboard, KYB steps, credentials, profile).
"""

from datetime import date, datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.auth import current_user
from app.db.session import get_db_session
from app.models.domain import User
from app.schemas.api import ApiModel
from app.services import developers as service
from app.services import sandbox
from app.services.document_store import (
    DocumentStorageError,
    DocumentTooLargeError,
    UnsupportedDocumentError,
)

router = APIRouter(prefix="/me/developer", tags=["developers"])


class DailyUsageView(ApiModel):
    day: date
    total: int
    successful: int


class UsageView(ApiModel):
    total_calls: int
    successful_calls: int
    #: The last 14 days, oldest first, for the usage chart.
    daily: list[DailyUsageView]


class ApiCallView(ApiModel):
    method: str
    #: The route template, e.g. /api/v1/trust/query.
    path: str
    status_code: int
    duration_ms: int
    at: datetime


class CredentialView(ApiModel):
    key_id: str | None
    #: "sandbox" or "production".
    environment: str
    created_at: datetime


class NameChangeView(ApiModel):
    new_name: str
    #: "under_review", "approved" or "rejected".
    status: str


class SandboxWorkerView(ApiModel):
    name: str
    role: str
    #: The trust band the demo history lands in.
    band: str
    #: Link this worker with POST /platform/worker-links using a sandbox key.
    consent_token: str


class DeveloperDashboard(ApiModel):
    email: str
    full_name: str | None
    business_name: str | None
    #: "not_started", "under_review", "approved" or "rejected".
    kyc_status: str
    kyb_status: str
    #: Why the last submission was sent back.
    review_note: str | None
    #: Step 1 is saved; step 2 is next.
    identity_submitted: bool
    usage: UsageView
    recent_activity: list[ApiCallView]
    credentials: list[CredentialView]
    name_change: NameChangeView | None
    sandbox_workers: list[SandboxWorkerView]


class CredentialsRequest(ApiModel):
    environment: str


class GeneratedCredentials(ApiModel):
    key_id: str
    #: Shown once; send it as X-API-Key.
    secret: str
    environment: str
    created_at: datetime


def _http_error(error: service.DeveloperError) -> HTTPException:
    if isinstance(error, service.NotADeveloperError):
        return HTTPException(status_code=404, detail=str(error))
    if isinstance(error, service.StepOutOfOrderError):
        return HTTPException(status_code=409, detail=str(error))
    return HTTPException(status_code=422, detail=str(error))


async def _read(upload: UploadFile) -> tuple[str, bytes]:
    content = await upload.read()
    await upload.close()
    return upload.filename or "document", content


async def _dashboard(session: AsyncSession, user: User) -> DeveloperDashboard:
    account = await service.account_for(session, user)
    usage = await service.usage(session, account)
    name_change = await service.open_name_change(session, account)
    return DeveloperDashboard(
        email=user.email,
        full_name=account.full_name,
        business_name=account.business_name,
        kyc_status=account.kyc_status.value,
        kyb_status=account.kyb_status.value,
        review_note=account.review_note,
        identity_submitted=service.identity_submitted(account),
        usage=UsageView(
            total_calls=usage.total_calls,
            successful_calls=usage.successful_calls,
            daily=[DailyUsageView(day=d.day, total=d.total, successful=d.successful) for d in usage.daily],
        ),
        recent_activity=[
            ApiCallView(method=row.method, path=row.path, status_code=row.status_code,
                        duration_ms=row.duration_ms, at=row.created_at)
            for row in usage.recent
        ],
        credentials=[
            CredentialView(key_id=key.key_id, environment=key.environment, created_at=key.created_at)
            for key in await service.credentials(session, account)
        ],
        name_change=NameChangeView(new_name=name_change.new_name, status=name_change.status.value)
        if name_change
        else None,
        sandbox_workers=[
            SandboxWorkerView(name=demo.name, role=demo.role, band=demo.band, consent_token=demo.consent_token)
            for demo in sandbox.DEMO_WORKERS
        ],
    )


async def _guarded(session: AsyncSession, action):
    """Run a step, mapping storage and domain failures onto status codes."""

    try:
        return await action()
    except (UnsupportedDocumentError, DocumentTooLargeError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except DocumentStorageError as error:
        raise HTTPException(
            status_code=503, detail="We could not upload your document. Try again in a moment."
        ) from error
    except service.DeveloperError as error:
        raise _http_error(error) from error


@router.get("", response_model=DeveloperDashboard, summary="The developer's dashboard")
async def dashboard(
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_db_session),
) -> DeveloperDashboard:
    try:
        return await _dashboard(session, user)
    except service.DeveloperError as error:
        raise _http_error(error) from error


@router.post("/identity", response_model=DeveloperDashboard, summary="Step 1: the developer's identity")
async def submit_identity(
    full_name: str = Form(..., min_length=2, max_length=160),
    document_type: str = Form(...),
    document: UploadFile = File(...),
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_db_session),
) -> DeveloperDashboard:
    upload = await _read(document)
    await _guarded(
        session,
        lambda: service.submit_identity(
            session, user, full_name=full_name, document_type=document_type, document=upload
        ),
    )
    await session.commit()
    return await _dashboard(session, user)


@router.post("/business", response_model=DeveloperDashboard, summary="Step 2: the registered business")
async def submit_business(
    business_name: str = Form(..., min_length=2, max_length=200),
    business_type: str = Form(...),
    registration_number: str = Form(..., min_length=2, max_length=40),
    tax_id: str = Form(..., min_length=2, max_length=40),
    confirmed: bool = Form(...),
    document: UploadFile = File(...),
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_db_session),
) -> DeveloperDashboard:
    """Sends both steps for an operator's review."""

    if not confirmed:
        raise HTTPException(status_code=422, detail="Confirm the information is accurate to continue.")
    upload = await _read(document)
    await _guarded(
        session,
        lambda: service.submit_business(
            session, user, business_name=business_name, business_type=business_type,
            registration_number=registration_number, tax_id=tax_id, document=upload,
        ),
    )
    await session.commit()
    return await _dashboard(session, user)


@router.post(
    "/credentials", response_model=GeneratedCredentials, status_code=201, summary="Generate API credentials"
)
async def generate_credentials(
    payload: CredentialsRequest,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_db_session),
) -> GeneratedCredentials:
    """The secret is in this response only; store it before leaving the screen."""

    key, secret = await _guarded(session, lambda: service.generate_credentials(session, user, payload.environment))
    await session.commit()
    return GeneratedCredentials(key_id=key.key_id, secret=secret, environment=key.environment, created_at=key.created_at)


@router.post("/name-change", response_model=DeveloperDashboard, summary="Ask to change the verified name")
async def request_name_change(
    new_name: str = Form(..., min_length=2, max_length=160),
    reason: str = Form(...),
    document: UploadFile | None = File(default=None),
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_db_session),
) -> DeveloperDashboard:
    upload = await _read(document) if document is not None and document.filename else None
    await _guarded(
        session,
        lambda: service.request_name_change(session, user, new_name=new_name, reason=reason, document=upload),
    )
    await session.commit()
    return await _dashboard(session, user)
