"""Role and worker/grant checks shared by review services; never changes sign-in."""

from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.admission import ReviewMembership
from app.models.domain import User, Worker
from app.models.portability import PlatformGrant, WorkerLink
from app.services.feature_common import FeatureError, now, aware


async def worker_for(
    session: AsyncSession, user: User, *, lock: bool = False
) -> Worker:
    """Resolve the authenticated worker; serialize mutations when requested."""
    query = select(Worker).where(Worker.user_id == user.id)
    worker = await session.scalar(query.with_for_update() if lock else query)
    if not user.is_active or worker is None:
        raise FeatureError(
            404, "WORKER_NOT_FOUND", "No worker profile is linked to this account."
        )
    return worker


async def reviewer(
    session: AsyncSession, user: User, scope: str, environment: str
) -> None:
    """Only explicitly assigned active session users can review a scope/environment."""
    role = await session.scalar(
        select(ReviewMembership).where(
            ReviewMembership.user_id == user.id,
            ReviewMembership.scope == scope,
            ReviewMembership.environment == environment,
            ReviewMembership.revoked_at.is_(None),
        )
    )
    if not user.is_active or role is None:
        raise FeatureError(
            403, "REVIEW_FORBIDDEN", "A reviewer role for this scope is required."
        )


async def consent(
    session: AsyncSession, worker_id: UUID, scope: str, environment: str
) -> None:
    """Recheck current platform consent and identity mapping, including at review time."""
    if scope == "first_party":
        return
    from app.models.portability import PlatformKey
    from app.models.domain import Worker as WorkerModel, User as UserModel
    from app.services import sandbox

    try:
        org = UUID(scope)
    except ValueError:
        raise FeatureError(403, "PLATFORM_SCOPE", "Invalid platform scope.") from None
    links = (
        await session.scalars(
            select(WorkerLink).where(
                WorkerLink.worker_id == worker_id, WorkerLink.organization_id == org
            )
        )
    ).all()
    for link in links:
        grant = await session.get(PlatformGrant, link.grant_id)
        if (
            grant
            and not grant.revoked_at
            and aware(grant.expires_at) > now()
            and "read_history" in grant.permissions
        ):
            # A sandbox role may not act on a real worker or vice versa.
            worker = await session.get(WorkerModel, worker_id)
            user = await session.get(UserModel, worker.user_id) if worker else None
            is_demo = bool(
                user and any(user.email == item.email for item in sandbox.DEMO_WORKERS)
            )
            if (environment == "sandbox") == is_demo:
                return
    raise FeatureError(
        403,
        "CONSENT_REQUIRED",
        "Current platform history consent and a worker mapping are required.",
    )
