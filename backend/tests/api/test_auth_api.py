"""Purpose: Verify the guarantor email + one-time code sign-in.

Dependencies: pytest, httpx ASGI transport, and the in-memory session fixture.
Used by: the backend test suite and CI.
"""

from datetime import UTC, datetime, timedelta

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.main import app
from app.models.domain import User, Worker
from app.services import auth as auth_service


def client_for(session: AsyncSession) -> AsyncClient:
    async def _session_override():
        yield session

    app.dependency_overrides[get_db_session] = _session_override
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def test_sign_in_sets_a_session_cookie(session: AsyncSession, worker: Worker) -> None:
    session.add(User(email="grace@example.com", display_name="Grace Guarantor"))
    await session.flush()

    async with client_for(session) as client:
        requested = await client.post("/api/v1/auth/code", json={"email": "grace@example.com"})
        assert requested.status_code == 200
        code = requested.json()["debug_code"]
        assert code is not None and len(code) == auth_service.CODE_LENGTH

        verified = await client.post(
            "/api/v1/auth/verify", json={"email": "grace@example.com", "code": code}
        )
        assert verified.status_code == 200, verified.text
        assert verified.json()["email"] == "grace@example.com"

        cookie = verified.headers.get("set-cookie", "")
        assert auth_service.SESSION_COOKIE in cookie
        assert "HttpOnly" in cookie

        me = await client.get("/api/v1/auth/me")
        assert me.status_code == 200
        assert me.json()["display_name"] == "Grace Guarantor"

    app.dependency_overrides.clear()


async def test_wrong_code_is_rejected(session: AsyncSession, worker: Worker) -> None:
    session.add(User(email="grace@example.com", display_name="Grace"))
    await session.flush()

    async with client_for(session) as client:
        await client.post("/api/v1/auth/code", json={"email": "grace@example.com"})
        response = await client.post(
            "/api/v1/auth/verify", json={"email": "grace@example.com", "code": "000000"}
        )
        assert response.status_code == 400

        me = await client.get("/api/v1/auth/me")
        assert me.status_code == 401

    app.dependency_overrides.clear()


async def test_unknown_address_does_not_reveal_itself(session: AsyncSession) -> None:
    async with client_for(session) as client:
        # Asking for a code looks identical whether or not an account exists.
        response = await client.post("/api/v1/auth/code", json={"email": "nobody@example.com"})
        assert response.status_code == 200
        assert response.json()["sent"] is True

    app.dependency_overrides.clear()


async def test_logout_ends_the_session(session: AsyncSession) -> None:
    session.add(User(email="grace@example.com", display_name="Grace"))
    await session.flush()

    async with client_for(session) as client:
        requested = await client.post("/api/v1/auth/code", json={"email": "grace@example.com"})
        await client.post(
            "/api/v1/auth/verify",
            json={"email": "grace@example.com", "code": requested.json()["debug_code"]},
        )
        assert (await client.get("/api/v1/auth/me")).status_code == 200

        assert (await client.post("/api/v1/auth/logout")).status_code == 204
        assert (await client.get("/api/v1/auth/me")).status_code == 401

    app.dependency_overrides.clear()


async def test_resend_is_rate_limited(session: AsyncSession) -> None:
    session.add(User(email="grace@example.com", display_name="Grace"))
    await session.flush()

    async with client_for(session) as client:
        assert (
            await client.post("/api/v1/auth/code", json={"email": "grace@example.com"})
        ).status_code == 200
        again = await client.post("/api/v1/auth/code", json={"email": "grace@example.com"})
        assert again.status_code == 429

    app.dependency_overrides.clear()


async def test_expired_code_is_refused(session: AsyncSession) -> None:
    session.add(User(email="grace@example.com", display_name="Grace"))
    await session.flush()

    issued_at = datetime.now(tz=UTC) - timedelta(minutes=20)
    code = await auth_service.request_login_code(session, "grace@example.com", now=issued_at)
    await session.flush()

    try:
        await auth_service.verify_login_code(session, "grace@example.com", code)
    except auth_service.InvalidCodeError as error:
        assert "expired" in str(error)
    else:  # pragma: no cover - the call must raise
        raise AssertionError("an expired code was accepted")


async def test_profile_can_be_read_and_updated(session: AsyncSession) -> None:
    session.add(User(email="grace@example.com", display_name="Grace"))
    await session.flush()

    async with client_for(session) as client:
        requested = await client.post("/api/v1/auth/code", json={"email": "grace@example.com"})
        await client.post(
            "/api/v1/auth/verify",
            json={"email": "grace@example.com", "code": requested.json()["debug_code"]},
        )

        before = await client.get("/api/v1/me/profile")
        assert before.status_code == 200
        assert before.json()["phone"] is None

        updated = await client.patch(
            "/api/v1/me/profile",
            json={
                "display_name": "Grace Guarantor",
                "phone": "+2348012345678",
                "address": "12 Trust Street, Lagos",
            },
        )
        assert updated.status_code == 200, updated.text
        assert updated.json()["display_name"] == "Grace Guarantor"
        assert updated.json()["phone"] == "+2348012345678"

        # The change sticks, and the email is untouched.
        again = await client.get("/api/v1/me/profile")
        assert again.json()["address"] == "12 Trust Street, Lagos"
        assert again.json()["email"] == "grace@example.com"

    app.dependency_overrides.clear()


async def test_profile_needs_a_session(session: AsyncSession) -> None:
    async with client_for(session) as client:
        assert (await client.get("/api/v1/me/profile")).status_code == 401
        assert (
            await client.patch("/api/v1/me/profile", json={"display_name": "Nobody"})
        ).status_code == 401

    app.dependency_overrides.clear()
