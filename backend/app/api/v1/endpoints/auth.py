"""Purpose: Expose the guarantor's email + one-time code sign-in.

Dependencies: FastAPI, SQLAlchemy async sessions, app.services.auth.
Used by: the guarantor sign-in screen and any endpoint needing the signed-in user.

The session is carried by an HTTP-only cookie, so page scripts cannot read it.
"""

from typing import Literal

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from pydantic import EmailStr, Field
from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_db_session
from app.models.developer import DeveloperAccount
from app.models.domain import AgreementStatus, GuarantorAgreement, User, Worker
from app.schemas.api import ApiModel
from app.services import auth as auth_service
from app.services import developers
from app.services.auth import (
    SESSION_COOKIE,
    AuthError,
    InvalidCodeError,
    ResendTooSoonError,
    UnknownAccountError,
)
from app.services.email_sender import EmailDeliveryError

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()


class RequestCodeRequest(ApiModel):
    email: EmailStr


class RequestCodeResponse(ApiModel):
    """Always reports success, so the response cannot be used to probe addresses."""

    sent: bool = True
    #: Present only outside production, so the flow is testable without email.
    debug_code: str | None = None


class VerifyCodeRequest(ApiModel):
    email: EmailStr
    code: str = Field(min_length=4, max_length=8)
    #: "developer" opens an account and a developer profile for a new address.
    #: Without it, only existing accounts sign in.
    sign_up: Literal["developer"] | None = None


class SignedInUser(ApiModel):
    user_id: str
    email: str
    display_name: str
    #: Has a worker profile.
    is_worker: bool = False
    #: Has been asked to stand behind a worker. Drafts the platform has not
    #: sent yet do not count.
    is_guarantor: bool = False
    #: Has a developer profile.
    is_developer: bool = False


async def _signed_in(session: AsyncSession, user: User) -> SignedInUser:
    """Who signed in, and which sides of the app they have, so the screens
    can send them to the right place."""

    is_worker = await session.scalar(select(exists().where(Worker.user_id == user.id)))
    is_guarantor = await session.scalar(
        select(
            exists().where(
                GuarantorAgreement.guarantor_user_id == user.id,
                GuarantorAgreement.status.not_in(
                    (AgreementStatus.DRAFT, AgreementStatus.REQUESTED)
                ),
            )
        )
    )
    is_developer = await session.scalar(select(exists().where(DeveloperAccount.user_id == user.id)))
    return SignedInUser(
        user_id=str(user.id),
        email=user.email,
        display_name=user.display_name,
        is_worker=bool(is_worker),
        is_guarantor=bool(is_guarantor),
        is_developer=bool(is_developer),
    )


def _http_error(error: AuthError) -> HTTPException:
    if isinstance(error, ResendTooSoonError):
        return HTTPException(status_code=429, detail=str(error))
    if isinstance(error, InvalidCodeError):
        return HTTPException(status_code=400, detail=str(error))
    if isinstance(error, UnknownAccountError):
        return HTTPException(status_code=404, detail=str(error))
    return HTTPException(status_code=400, detail=str(error))


def _is_development() -> bool:
    return settings.environment == "development"


async def current_user(
    guarantor_session: str | None = Cookie(default=None, alias=SESSION_COOKIE),
    session: AsyncSession = Depends(get_db_session),
) -> User:
    """Dependency for endpoints that need a signed-in guarantor."""

    if not guarantor_session:
        raise HTTPException(status_code=401, detail="Sign in to continue.")

    user = await auth_service.resolve_session(session, guarantor_session)
    if user is None:
        raise HTTPException(status_code=401, detail="Your session has expired. Sign in again.")

    return user


@router.post("/code", response_model=RequestCodeResponse, summary="Email a login code")
async def request_code(
    payload: RequestCodeRequest,
    session: AsyncSession = Depends(get_db_session),
) -> RequestCodeResponse:
    try:
        code = await auth_service.request_login_code(session, payload.email)
    except AuthError as error:
        raise _http_error(error) from error
    except EmailDeliveryError as error:
        # The provider refused it; the code was never stored, so retrying is safe.
        raise HTTPException(
            status_code=502, detail="We could not send the code. Try again in a moment."
        ) from error

    await session.commit()
    # Never leak the code outside development.
    return RequestCodeResponse(debug_code=code if _is_development() else None)


@router.post("/verify", response_model=SignedInUser, summary="Verify a login code")
async def verify_code(
    payload: VerifyCodeRequest,
    response: Response,
    session: AsyncSession = Depends(get_db_session),
) -> SignedInUser:
    try:
        user, token = await auth_service.verify_login_code(
            session, payload.email, payload.code, create_account=payload.sign_up is not None
        )
    except AuthError as error:
        # Attempt counters and consumed codes must survive a rejection.
        await session.commit()
        raise _http_error(error) from error

    if payload.sign_up == "developer":
        await developers.ensure_developer(session, user)
    await session.commit()
    response.set_cookie(
        SESSION_COOKIE,
        token,
        httponly=True,
        samesite="lax",
        secure=not _is_development(),
        max_age=int(auth_service.SESSION_TTL.total_seconds()),
        path="/",
    )
    return await _signed_in(session, user)


@router.get("/me", response_model=SignedInUser, summary="Who is signed in")
async def me(
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_db_session),
) -> SignedInUser:
    return await _signed_in(session, user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, summary="End the session")
async def logout(
    response: Response,
    guarantor_session: str | None = Cookie(default=None, alias=SESSION_COOKIE),
    session: AsyncSession = Depends(get_db_session),
) -> None:
    if guarantor_session:
        await auth_service.end_session(session, guarantor_session)
        await session.commit()

    response.delete_cookie(SESSION_COOKIE, path="/")
