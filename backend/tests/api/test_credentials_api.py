"""Verify authenticated credential export/import endpoints."""

from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints import auth as auth_endpoint
from app.api.v1.endpoints import credentials as credentials_endpoint
from app.db.session import get_db_session
from app.main import app
from app.models.domain import User, Worker


@pytest.mark.asyncio
async def test_worker_can_export_and_import_own_signed_bundle(
    session: AsyncSession, worker: Worker, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = await session.get(User, worker.user_id)
    assert user is not None
    monkeypatch.setattr(credentials_endpoint.settings, "credential_signing_secret", "k" * 32)

    async def override_session() -> AsyncGenerator[AsyncSession, None]:
        yield session

    async def override_user() -> User:
        return user

    app.dependency_overrides[get_db_session] = override_session
    app.dependency_overrides[auth_endpoint.current_user] = override_user
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            exported = await client.get(f"/api/v1/workers/{worker.id}/credentials/export")
            assert exported.status_code == 200
            export_payload = exported.json()
            assert export_payload["worker_id"] == str(worker.id)
            assert export_payload["trust_summary"]["band"] == "Building History"
            assert export_payload["verified_outcomes"] == []

            imported = await client.post(
                f"/api/v1/workers/{worker.id}/credentials/import",
                json={
                    "credential_token": export_payload["credential_token"],
                    "source_platform": "test-platform",
                },
            )
    finally:
        app.dependency_overrides.pop(get_db_session, None)
        app.dependency_overrides.pop(auth_endpoint.current_user, None)

    assert imported.status_code == 200
    assert imported.json()["imported_outcomes"] == 0
    assert imported.json()["new_band"] == "Building History"
