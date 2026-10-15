"""Purpose: Verify the live demo signs visitors in as a read-only worker.

Dependencies: pytest, httpx ASGI transport, and the in-memory session fixture.
Used by: the backend test suite and CI.
"""

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_db_session
from app.main import app
from app.models.domain import User, Worker
from app.services import auth as auth_service


def client_for(session: AsyncSession) -> AsyncClient:
    async def _session_override():
        yield session

    app.dependency_overrides[get_db_session] = _session_override
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def seed_demo_worker(session: AsyncSession) -> User:
    user = User(email=get_settings().demo_worker_email, display_name="Jane Adams")
    session.add(user)
    await session.flush()
    session.add(Worker(user_id=user.id, role="Cleaner"))
    await session.flush()
    return user


async def test_the_demo_needs_its_worker_seeded(session: AsyncSession) -> None:
    async with client_for(session) as client:
        response = await client.post("/api/v1/auth/demo")
        assert response.status_code == 404

    app.dependency_overrides.clear()


async def test_the_demo_signs_in_as_the_demo_worker(session: AsyncSession) -> None:
    await seed_demo_worker(session)

    async with client_for(session) as client:
        response = await client.post("/api/v1/auth/demo")
        assert response.status_code == 200, response.text
        assert response.json()["is_demo"] is True
        assert response.json()["is_worker"] is True
        assert auth_service.SESSION_COOKIE in response.headers.get("set-cookie", "")

        me = await client.get("/api/v1/auth/me")
        assert me.status_code == 200
        assert me.json()["is_demo"] is True

    app.dependency_overrides.clear()


async def test_the_demo_worker_cannot_change_anything(session: AsyncSession) -> None:
    await seed_demo_worker(session)

    async with client_for(session) as client:
        await client.post("/api/v1/auth/demo")

        # Looking is fine.
        assert (await client.get("/api/v1/me/record")).status_code == 200

        changed = await client.post("/api/v1/auth/email-change/code", json={"email": "me@example.com"})
        assert changed.status_code == 403
        assert "demo account" in changed.json()["detail"]

        # Leaving the demo still works.
        assert (await client.post("/api/v1/auth/logout")).status_code == 204
        assert (await client.get("/api/v1/auth/me")).status_code == 401

    app.dependency_overrides.clear()


async def test_other_accounts_are_not_the_demo(session: AsyncSession) -> None:
    await seed_demo_worker(session)
    user = User(email="grace@example.com", display_name="Grace")
    session.add(user)
    await session.flush()
    token = auth_service.open_session(session, user)
    await session.flush()

    async with client_for(session) as client:
        client.cookies.set(auth_service.SESSION_COOKIE, token)
        me = await client.get("/api/v1/auth/me")
        assert me.json()["is_demo"] is False

    app.dependency_overrides.clear()
