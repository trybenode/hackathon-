"""Purpose: Expose the developer dashboard, verification steps and credentials.

Dependencies: FastAPI, SQLAlchemy async sessions, app.services.developers.
Used by: the developer screens (dashboard, KYB steps, credentials, profile).
"""

from datetime import date, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from pydantic import Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.auth import current_user
from app.core.platform_auth import SCOPES
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
    #: The demo guarantee: "active", "pending", "expired", or null for none.
    guarantor: str | None
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


#: What each access group lets a key do, for the key screens.
ACCESS_DESCRIPTIONS = {
    "trust": "Link workers with their consent and ask for trust assessments.",
    "history": "Read a linked worker's work history and import your own records.",
    "guarantees": "View a worker's guarantees and ask for, trigger or revoke your own.",
    "scoring": "Read and change how your platform's trust scores are calculated.",
}


class AccessGroupView(ApiModel):
    id: str
    label: str
    description: str


class ApiKeyView(ApiModel):
    id: UUID
    name: str
    #: Public; safe to show and copy. The secret is never shown again.
    key_id: str | None
    #: "sandbox" or "production"; fixed when the key is made.
    environment: str
    #: The groups this key may use; null is full access, future features included.
    scopes: list[str] | None
    #: Operator-approved: imported records count as verified.
    can_attest: bool
    created_at: datetime
    last_used_at: datetime | None
    #: Calls over the last 14 days.
    recent_calls: int


class ApiKeyList(ApiModel):
    items: list[ApiKeyView]
    access_groups: list[AccessGroupView]
    #: Active keys allowed per environment.
    max_active_per_environment: int


class ApiKeyCreate(ApiModel):
    name: str = Field(min_length=1, max_length=80)
    environment: str
    #: Omit or null for full access.
    scopes: list[str] | None = None


class ApiKeyUpdate(ApiModel):
    name: str = Field(min_length=1, max_length=80)
    #: Null for full access.
    scopes: list[str] | None


class ApiKeySecret(ApiModel):
    key: ApiKeyView
    #: Shown once; send it as X-API-Key.
    secret: str


def _http_error(error: service.DeveloperError) -> HTTPException:
    if isinstance(error, service.NotADeveloperError):
        return HTTPException(status_code=404, detail=str(error))
    if isinstance(error, service.KeyNotFoundError):
        return HTTPException(status_code=404, detail=str(error))
    if isinstance(error, (service.StepOutOfOrderError, service.LimitReachedError)):
        return HTTPException(status_code=409, detail=str(error))
    return HTTPException(status_code=422, detail=str(error))


def _key_view(key, calls: dict) -> ApiKeyView:
    return ApiKeyView(
        id=key.id,
        name=key.name or "API key",
        key_id=key.key_id,
        environment=key.environment,
        scopes=key.scopes,
        can_attest=key.can_attest,
        created_at=key.created_at,
        last_used_at=key.last_used_at,
        recent_calls=calls.get(key.id, 0),
    )


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
            SandboxWorkerView(
                name=demo.name, role=demo.role, band=demo.band, guarantor=demo.guarantee,
                consent_token=demo.consent_token,
            )
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


@router.get("/keys", response_model=ApiKeyList, summary="Your active API keys")
async def list_keys(
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ApiKeyList:
    """Revoked keys are hidden; secrets are never returned here."""

    async def build() -> ApiKeyList:
        account = await service.account_for(session, user)
        calls = await service.calls_per_key(session, account)
        return ApiKeyList(
            items=[_key_view(key, calls) for key in await service.credentials(session, account)],
            access_groups=[
                AccessGroupView(id=group, label=label, description=ACCESS_DESCRIPTIONS[group])
                for group, label in SCOPES.items()
            ],
            max_active_per_environment=service.MAX_ACTIVE_KEYS,
        )

    return await _guarded(session, build)


@router.post("/keys", response_model=ApiKeySecret, status_code=201, summary="Create an API key")
async def create_key(
    payload: ApiKeyCreate,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ApiKeySecret:
    """The secret is in this response only; store it before leaving the screen."""

    key, secret = await _guarded(
        session,
        lambda: service.create_key(
            session, user, environment=payload.environment, name=payload.name, scopes=payload.scopes
        ),
    )
    await session.commit()
    return ApiKeySecret(key=_key_view(key, {}), secret=secret)


@router.patch("/keys/{key_id}", response_model=ApiKeyView, summary="Rename a key or change its access")
async def update_key(
    key_id: UUID,
    payload: ApiKeyUpdate,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ApiKeyView:
    key = await _guarded(
        session, lambda: service.update_key(session, user, key_id, name=payload.name, scopes=payload.scopes)
    )
    await session.commit()
    return _key_view(key, {})


@router.post("/keys/{key_id}/rotate", response_model=ApiKeySecret, summary="Replace a key's secret")
async def rotate_key(
    key_id: UUID,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ApiKeySecret:
    """The old secret stops working at once; the new one is shown only here."""

    key, secret = await _guarded(session, lambda: service.rotate_key(session, user, key_id))
    await session.commit()
    return ApiKeySecret(key=_key_view(key, {}), secret=secret)


@router.delete("/keys/{key_id}", status_code=204, summary="Revoke a key")
async def revoke_key(
    key_id: UUID,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    """The key stops working at once and leaves the list. This cannot be undone."""

    await _guarded(session, lambda: service.revoke_key(session, user, key_id))
    await session.commit()
    return Response(status_code=204)


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
