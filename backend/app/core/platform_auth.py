"""Purpose: Require the configured platform API key for B2B endpoints.

Dependencies: hmac, FastAPI headers/errors, and app.core.config.
Used by: platform-facing trust and outcome routes.
"""

import hmac

from fastapi import Header, HTTPException, status

from app.core.config import get_settings


async def require_platform_api_key(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> None:
    """Validate the shared MVP platform key without logging its value."""

    expected_key = get_settings().platform_api_key
    if not expected_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Platform API authentication is not configured",
        )
    if not x_api_key or not hmac.compare_digest(x_api_key, expected_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="A valid platform API key is required",
            headers={"WWW-Authenticate": "ApiKey"},
        )
