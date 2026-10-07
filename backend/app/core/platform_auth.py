"""Platform-key authentication; legacy shared keys are development-only."""
import hmac
from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import get_settings
from app.db.session import get_db_session
from app.models.portability import PlatformKey
from app.services.portability import digest


async def require_platform_api_key(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    session: AsyncSession = Depends(get_db_session),
) -> PlatformKey | None:
    """Resolve a tenant key; None denotes the explicitly limited dev legacy key."""
    settings = get_settings()
    if x_api_key:
        principal = await session.scalar(select(PlatformKey).where(PlatformKey.key_hash == digest(x_api_key), PlatformKey.revoked_at.is_(None)))
        if principal:
            return principal
        if settings.environment == "development" and settings.platform_api_key and hmac.compare_digest(x_api_key, settings.platform_api_key):
            return None
    if not settings.platform_api_key and not x_api_key:
        raise HTTPException(status_code=503, detail="Platform API authentication is not configured")
    raise HTTPException(status_code=401, detail="A valid platform API key is required", headers={"WWW-Authenticate": "ApiKey"})


async def require_tenant(principal: PlatformKey | None = Depends(require_platform_api_key)) -> PlatformKey:
    """Reject shared legacy keys at all platform history endpoints."""
    if principal is None:
        raise HTTPException(status_code=403, detail="A dedicated platform API key is required")
    return principal
