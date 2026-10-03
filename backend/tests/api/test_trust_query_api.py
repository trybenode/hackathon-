"""Verify `/trust/query` delegates to the shared persisted-history scorer."""

from collections.abc import AsyncGenerator
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.core.config import get_settings
from app.main import app
from app.models.domain import User, Worker


@pytest.mark.asyncio
async def test_trust_query_returns_building_history_for_new_worker(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(get_settings(), "platform_api_key", "test-platform-key")
    user = User(email=f"new-{uuid4()}@example.test", display_name="New Worker")
    session.add(user)
    await session.flush()
    worker = Worker(user_id=user.id)
    session.add(worker)
    await session.flush()

    async def override_session() -> AsyncGenerator[AsyncSession, None]:
        yield session

    app.dependency_overrides[get_db_session] = override_session
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/trust/query",
                json={
                    "worker_id": str(worker.id),
                    "platform_type": "generic",
                    "job_context": {"job_type": "cleaning", "value_band": "low"},
                },
                headers={"X-API-Key": "test-platform-key"},
            )
    finally:
        app.dependency_overrides.pop(get_db_session, None)

    assert response.status_code == 200
    payload = response.json()
    assert payload["decision"] is False
    assert payload["confidence"] == 0
    assert payload["band"] == "Building History"
    assert payload["status"] == "Building History"


@pytest.mark.asyncio
async def test_trust_query_requires_platform_authentication(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(get_settings(), "platform_api_key", "test-platform-key")
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/trust/query",
            json={
                "worker_id": str(uuid4()),
                "platform_type": "generic",
                "job_context": {"job_type": "cleaning", "value_band": "low"},
            },
        )

    assert response.status_code == 401
