"""Purpose: Serve the signed-in guarantor's own dashboard data.

Dependencies: FastAPI, SQLAlchemy async sessions, app.services.dashboard.
Used by: the guarantor dashboard screens.

Every route here is scoped to the session's user, so a guarantor can only read
instruments they stand behind.
"""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.auth import current_user
from app.db.session import get_db_session
from app.models.domain import User
from app.schemas.api import ApiModel
from app.services import dashboard as dashboard_service

router = APIRouter(prefix="/me", tags=["dashboard"])


class GuaranteeCard(ApiModel):
    instrument_id: UUID
    reference: str
    worker_name: str
    worker_role: str | None = None
    avatar_url: str | None = None
    status: str
    #: Which tab shows this card: "pending", "active", "expired" or "closed".
    bucket: str
    #: When the year began; empty until both identity checks pass.
    started_on: datetime | None = None
    valid_until: datetime
    ended_on: datetime | None = None


class ActivityItem(ApiModel):
    id: UUID
    label: str
    at: datetime


class GuaranteeDetailResponse(ApiModel):
    guarantee: GuaranteeCard
    relationship: str
    scope: str
    conditions: str
    signed_at: datetime | None = None
    activity: list[ActivityItem]
    agreement: list[str]


class DashboardResponse(ApiModel):
    greeting_name: str
    active_count: int
    completed_count: int
    guarantees: list[GuaranteeCard]
    recent_activity: list[ActivityItem]
    action_required: GuaranteeCard | None = None


class ProfileUpdateRequest(ApiModel):
    """What a guarantor may change about themselves.

    The email is left out on purpose: it identifies the account, so changing
    it belongs to the sign-in flow rather than a profile form.
    """

    display_name: str = Field(min_length=1, max_length=160)
    phone: str | None = Field(default=None, max_length=40)
    address: str | None = Field(default=None, max_length=500)


class ProfileResponse(ApiModel):
    user_id: UUID
    email: str
    display_name: str
    phone: str | None = None
    address: str | None = None


class NotificationItem(ApiModel):
    id: str
    title: str
    body: str
    at: datetime
    icon: str


def _card(source: dashboard_service.DashboardGuarantee) -> GuaranteeCard:
    return GuaranteeCard(
        instrument_id=source.instrument_id,
        reference=source.reference,
        worker_name=source.worker_name,
        worker_role=source.worker_role,
        avatar_url=source.avatar_url,
        status=source.status,
        bucket=source.bucket,
        started_on=source.started_on,
        valid_until=source.valid_until,
        ended_on=source.ended_on,
    )


async def _load_guarantee(
    session: AsyncSession, user: User, instrument_id: UUID
) -> dashboard_service.GuaranteeDetail:
    try:
        return await dashboard_service.load_guarantee(session, user.id, instrument_id)
    except dashboard_service.GuaranteeNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.get("/dashboard", response_model=DashboardResponse, summary="The guarantor's overview")
async def dashboard(
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_db_session),
) -> DashboardResponse:
    summary = await dashboard_service.load_summary(session, user.id)

    return DashboardResponse(
        # The greeting uses the first name, as the design shows.
        greeting_name=user.display_name.split(" ")[0],
        active_count=summary.active_count,
        completed_count=summary.completed_count,
        guarantees=[_card(card) for card in summary.guarantees],
        recent_activity=[
            ActivityItem(id=entry.id, label=entry.label, at=entry.at)
            for entry in summary.recent_activity
        ],
        action_required=_card(summary.action_required) if summary.action_required else None,
    )


@router.get("/profile", response_model=ProfileResponse, summary="The guarantor's profile")
async def profile(user: User = Depends(current_user)) -> ProfileResponse:
    return ProfileResponse(
        user_id=user.id,
        email=user.email,
        display_name=user.display_name,
        phone=user.phone,
        address=user.address,
    )


@router.patch("/profile", response_model=ProfileResponse, summary="Update the profile")
async def update_profile(
    payload: ProfileUpdateRequest,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ProfileResponse:
    user.display_name = payload.display_name.strip()
    # Empty strings from the form mean "cleared", not "unchanged".
    user.phone = (payload.phone or "").strip() or None
    user.address = (payload.address or "").strip() or None

    await session.commit()
    return ProfileResponse(
        user_id=user.id,
        email=user.email,
        display_name=user.display_name,
        phone=user.phone,
        address=user.address,
    )


@router.get(
    "/notifications",
    response_model=list[NotificationItem],
    summary="Alerts derived from the guarantor's instruments",
)
async def notifications(
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[NotificationItem]:
    items = await dashboard_service.load_notifications(session, user.id)

    return [
        NotificationItem(id=item.id, title=item.title, body=item.body, at=item.at, icon=item.icon)
        for item in items
    ]


@router.get(
    "/guarantees/{instrument_id}",
    response_model=GuaranteeDetailResponse,
    summary="One of the guarantor's guarantees, with its history",
)
async def guarantee_detail(
    instrument_id: UUID,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_db_session),
) -> GuaranteeDetailResponse:
    detail = await _load_guarantee(session, user, instrument_id)

    return GuaranteeDetailResponse(
        guarantee=_card(detail.card),
        relationship=detail.relationship,
        scope=detail.scope,
        conditions=detail.conditions,
        signed_at=detail.signed_at,
        activity=[
            ActivityItem(id=entry.id, label=entry.label, at=entry.at) for entry in detail.activity
        ],
        agreement=detail.agreement,
    )


@router.get(
    "/guarantees/{instrument_id}/agreement",
    response_class=PlainTextResponse,
    summary="Download the agreement as a text file",
)
async def guarantee_agreement(
    instrument_id: UUID,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_db_session),
) -> PlainTextResponse:
    detail = await _load_guarantee(session, user, instrument_id)
    reference = detail.card.reference
    body = "\n\n".join([f"Guarantee agreement {reference}", *detail.agreement]) + "\n"

    return PlainTextResponse(
        body,
        headers={"Content-Disposition": f'attachment; filename="agreement-{reference}.txt"'},
    )
