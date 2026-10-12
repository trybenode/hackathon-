"""Platform-key authentication; legacy shared keys are development-only."""
import hmac
from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.api_usage import mark_platform_call
from app.core.config import get_settings
from app.db.session import get_db_session
from app.models.portability import PlatformKey
from app.services.portability import FeatureError, digest


async def require_platform_api_key(
    request: Request,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    session: AsyncSession = Depends(get_db_session),
) -> PlatformKey | None:
    """Resolve a tenant key; None denotes the explicitly limited dev legacy key."""
    settings = get_settings()
    if x_api_key:
        principal = await session.scalar(select(PlatformKey).where(PlatformKey.key_hash == digest(x_api_key), PlatformKey.revoked_at.is_(None)))
        if principal:
            # Counted on the developer dashboard once the response is known.
            mark_platform_call(request, principal.id, principal.organization_id)
            return principal
        if settings.environment == "development" and settings.platform_api_key and hmac.compare_digest(x_api_key, settings.platform_api_key):
            return None
    # Platforms have their own keys now, so a missing or wrong key is always
    # the caller's to fix, whether or not the dev legacy key is configured.
    raise HTTPException(status_code=401, detail="A valid platform API key is required", headers={"WWW-Authenticate": "ApiKey"})


async def require_tenant(principal: PlatformKey | None = Depends(require_platform_api_key)) -> PlatformKey:
    """Reject shared legacy keys at all platform history endpoints."""
    if principal is None:
        raise HTTPException(status_code=403, detail="A dedicated platform API key is required")
    return principal


#: The access groups a key can be limited to, as the dashboard names them.
SCOPES = {
    "trust": "Trust & workers",
    "history": "Work history",
    "guarantees": "Guarantees",
    "scoring": "Scoring settings",
}


def _check_scope(principal: PlatformKey | None, scope: str) -> None:
    # No scopes means full access, including features added later.
    if principal is not None and principal.scopes is not None and scope not in principal.scopes:
        raise FeatureError(403, "SCOPE_REQUIRED",
            f"This API key has no {SCOPES[scope]} access. Edit the key's access on the dashboard.")


def require_scope(scope: str):
    """A platform key (or the dev legacy key) allowed to use `scope`."""
    async def dependency(principal: PlatformKey | None = Depends(require_platform_api_key)) -> PlatformKey | None:
        _check_scope(principal, scope)
        return principal
    return dependency


def require_tenant_scope(scope: str):
    """A dedicated platform key allowed to use `scope`."""
    async def dependency(principal: PlatformKey = Depends(require_tenant)) -> PlatformKey:
        _check_scope(principal, scope)
        return principal
    return dependency
