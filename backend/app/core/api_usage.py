"""Purpose: Record each call made with a platform key for the developer dashboard.

Dependencies: Starlette middleware, app.db.session and app.models.developer.
Used by: app.main; the platform-key check marks the request with its key.

Only the method, route template, status and duration are kept: no bodies, no
headers, and no worker identifiers (the template keeps `{external_id}`).
"""

import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.db.session import get_db_session
from app.models.developer import ApiRequestLog

logger = logging.getLogger(__name__)


def mark_platform_call(request: Request, key_id, organization_id) -> None:
    """Called once a platform key is accepted, so the call gets logged."""

    request.state.platform_call = (key_id, organization_id)


class ApiUsageMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        started = time.perf_counter()
        response = await call_next(request)
        marked = getattr(request.state, "platform_call", None)
        if marked is not None:
            route = request.scope.get("route")
            await self._record(
                request,
                ApiRequestLog(
                    platform_key_id=marked[0],
                    organization_id=marked[1],
                    method=request.method,
                    path=getattr(route, "path", request.url.path)[:300],
                    status_code=response.status_code,
                    duration_ms=int((time.perf_counter() - started) * 1000),
                ),
            )
        return response

    async def _record(self, request: Request, row: ApiRequestLog) -> None:
        # Tests swap the database through the dependency override; use it too.
        provider = request.app.dependency_overrides.get(get_db_session, get_db_session)
        sessions = provider()
        try:
            session = await anext(sessions)
            session.add(row)
            await session.commit()
        except Exception:  # A lost usage row must never fail the call itself.
            logger.warning("Could not record platform API usage", exc_info=True)
        finally:
            await sessions.aclose()
