"""Purpose: Expose a new worker's verification steps over HTTP.

Dependencies: FastAPI, SQLAlchemy async sessions, app.services.worker_onboarding.
Used by: the worker onboarding screens (identity, liveness, add guarantor) and
the worker Home, which locks job creation until a guarantor is active.
"""

from datetime import date, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.auth import current_user
from app.core.config import get_settings
from app.db.session import get_db_session
from app.models.domain import User
from app.schemas.api import ApiModel, GuarantorRelationship
from app.services import worker_onboarding as onboarding
from app.services.document_store import (
    DocumentStorageError,
    DocumentTooLargeError,
    UnsupportedDocumentError,
)
from app.services.identity_provider import IdentitySubmission, LivenessSubmission

router = APIRouter(prefix="/me/worker", tags=["worker onboarding"])
settings = get_settings()


class GuarantorInviteView(ApiModel):
    instrument_id: UUID
    name: str
    relationship: str
    #: "Pending Signature", "Pending Verification" or "Active".
    status: str
    expires_at: datetime
    #: The page the worker sends their guarantor.
    link: str


class OnboardingResponse(ApiModel):
    identity_verified: bool
    liveness_verified: bool
    #: "none", "pending" or "active". Job links need "active".
    guarantor: str
    #: "identity", "liveness", "guarantor", or null once nothing is left.
    next_step: str | None
    invite: GuarantorInviteView | None = None


class GuarantorInviteRequest(ApiModel):
    first_name: str = Field(min_length=1, max_length=80)
    last_name: str = Field(min_length=1, max_length=80)
    relationship: GuarantorRelationship


def _invite_view(invite: onboarding.GuarantorInvite) -> GuarantorInviteView:
    base = settings.frontend_base_url.rstrip("/")
    return GuarantorInviteView(
        instrument_id=invite.instrument_id,
        name=invite.name,
        relationship=invite.relationship,
        status=invite.status,
        expires_at=invite.expires_at,
        link=f"{base}/guarantor/{invite.instrument_id}/review",
    )


async def _progress(session: AsyncSession, user: User) -> OnboardingResponse:
    status = await onboarding.status(session, user)
    return OnboardingResponse(
        identity_verified=status.identity_verified,
        liveness_verified=status.liveness_verified,
        guarantor=status.guarantor,
        next_step=status.next_step,
        invite=_invite_view(status.invite) if status.invite else None,
    )


def _http_error(error: onboarding.OnboardingError) -> HTTPException:
    if isinstance(error, onboarding.NotAWorkerError):
        return HTTPException(status_code=404, detail=str(error))
    if isinstance(error, onboarding.StepOutOfOrderError):
        return HTTPException(status_code=409, detail=str(error))
    return HTTPException(status_code=422, detail=str(error))


@router.get("/onboarding", response_model=OnboardingResponse, summary="Where the worker is in onboarding")
async def onboarding_status(
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_db_session),
) -> OnboardingResponse:
    try:
        return await _progress(session, user)
    except onboarding.OnboardingError as error:
        raise _http_error(error) from error


@router.post("/identity", response_model=OnboardingResponse, summary="Submit the worker's identity details")
async def submit_identity(
    first_name: str = Form(..., min_length=1, max_length=80),
    last_name: str = Form(..., min_length=1, max_length=80),
    date_of_birth: date = Form(...),
    phone: str = Form(..., min_length=5, max_length=40),
    address: str = Form(..., min_length=1, max_length=500),
    nin: str = Form(..., max_length=20),
    bvn: str = Form(..., max_length=20),
    utility_bill: UploadFile | None = File(default=None),
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_db_session),
) -> OnboardingResponse:
    """Forward the details to the provider; NIN and BVN are never stored.

    The utility bill goes to object storage and only its key is kept.
    """

    document: tuple[str, bytes] | None = None
    if utility_bill is not None and utility_bill.filename:
        document = (utility_bill.filename, await utility_bill.read())
        await utility_bill.close()

    submission = IdentitySubmission(
        first_name=first_name.strip(),
        last_name=last_name.strip(),
        phone=phone.strip(),
        address=address.strip(),
        nin=nin.strip(),
        bvn=bvn.strip(),
        date_of_birth=date_of_birth,
    )
    try:
        await onboarding.submit_identity(session, user, submission, document=document)
    except (UnsupportedDocumentError, DocumentTooLargeError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except DocumentStorageError as error:
        raise HTTPException(
            status_code=503, detail="We could not upload your document. Try again in a moment."
        ) from error
    except onboarding.OnboardingError as error:
        # A failed check is still recorded.
        await session.commit()
        raise _http_error(error) from error

    await session.commit()
    return await _progress(session, user)


@router.post("/liveness", response_model=OnboardingResponse, summary="Check the worker's liveness capture")
async def complete_liveness(
    frame: UploadFile = File(...),
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_db_session),
) -> OnboardingResponse:
    """The frame goes to the provider and is dropped; only the reference is kept."""

    image = await frame.read()
    await frame.close()
    try:
        await onboarding.complete_liveness(
            session, user, LivenessSubmission(image=image, content_type=frame.content_type or "image/jpeg")
        )
    except onboarding.OnboardingError as error:
        await session.commit()
        raise _http_error(error) from error

    await session.commit()
    return await _progress(session, user)


@router.post(
    "/guarantor",
    response_model=GuarantorInviteView,
    status_code=201,
    summary="Create an invite link for the worker's guarantor",
)
async def invite_guarantor(
    payload: GuarantorInviteRequest,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_db_session),
) -> GuarantorInviteView:
    """The link expires in seven days; a new invite replaces an unclaimed one."""

    try:
        invite = await onboarding.invite_guarantor(
            session,
            user,
            first_name=payload.first_name.strip(),
            last_name=payload.last_name.strip(),
            relationship=payload.relationship.value,
        )
    except onboarding.OnboardingError as error:
        raise _http_error(error) from error

    await session.commit()
    return _invite_view(invite)
