"""Purpose: Verify the health endpoint returns API and database readiness.

Dependencies: pytest, httpx, and the FastAPI application.
Used by: the backend test suite and CI.
"""

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.v1.endpoints.health import get_db_session
from app.main import app


class _TestSession:
    async def execute(self, statement: object) -> None:
        return None


async def _test_session():
    yield _TestSession()


@pytest.mark.asyncio
async def test_health_check() -> None:
    app.dependency_overrides[get_db_session] = _test_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/health")
    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "trust-infrastructure-api",
        "database": "ok",
    }
