"""Purpose: Verify email + one-time code sign-in, worker sign-up and invite claims.

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


async def test_sign_in_reports_which_sides_the_account_has(
    session: AsyncSession, worker: Worker
) -> None:
    """Worker, guarantor, both, or neither: the screens route on these flags."""

    from app.models.domain import AgreementStatus, GuarantorAgreement

    guarantor = User(email="grace@example.com", display_name="Grace")
    drafted = User(email="draft@example.com", display_name="Drafted")
    session.add_all([guarantor, drafted])
    await session.flush()
    for person, status in ((guarantor, AgreementStatus.PENDING_SIGNATURE), (drafted, AgreementStatus.DRAFT)):
        session.add(
            GuarantorAgreement(
                worker_id=worker.id,
                guarantor_user_id=person.id,
                scope="Cleaning",
                conditions="No-show",
                relationship_type="sibling",
                status=status,
                valid_until=datetime.now(tz=UTC) + timedelta(days=7),
            )
        )
    # The worker also stands behind someone, so they are both.
    session.add(
        GuarantorAgreement(
            worker_id=worker.id,
            guarantor_user_id=worker.user_id,
            scope="Cleaning",
            conditions="No-show",
            relationship_type="colleague",
            status=AgreementStatus.ACTIVE,
            valid_until=datetime.now(tz=UTC) + timedelta(days=300),
        )
    )
    await session.flush()

    async def roles(email: str) -> tuple[bool, bool]:
        async with client_for(session) as client:
            requested = await client.post("/api/v1/auth/code", json={"email": email})
            verified = await client.post(
                "/api/v1/auth/verify",
                json={"email": email, "code": requested.json()["debug_code"]},
            )
            body = verified.json()
            me = (await client.get("/api/v1/auth/me")).json()
            assert (me["is_worker"], me["is_guarantor"]) == (body["is_worker"], body["is_guarantor"])
            return body["is_worker"], body["is_guarantor"]

    assert await roles("worker@example.com") == (True, True)
    assert await roles("grace@example.com") == (False, True)
    # A draft has not been sent, so it does not make anyone a guarantor yet.
    assert await roles("draft@example.com") == (False, False)

    app.dependency_overrides.clear()


async def sign_in(client: AsyncClient, email: str, **extra) -> dict:
    requested = await client.post("/api/v1/auth/code", json={"email": email})
    verified = await client.post(
        "/api/v1/auth/verify",
        json={"email": email, "code": requested.json()["debug_code"], **extra},
    )
    assert verified.status_code == 200, verified.text
    return verified.json()


async def test_a_new_worker_signs_up_with_a_code(session: AsyncSession) -> None:
    async with client_for(session) as client:
        body = await sign_in(client, "Newbie@Example.com", sign_up="worker")

    assert body["email"] == "newbie@example.com"
    assert body["is_worker"] is True
    # Straight on to the identity details.
    assert body["onboarding_step"] == "identity"
    app.dependency_overrides.clear()


async def test_sign_up_without_a_role_is_still_refused(session: AsyncSession) -> None:
    async with client_for(session) as client:
        requested = await client.post("/api/v1/auth/code", json={"email": "nobody@example.com"})
        verified = await client.post(
            "/api/v1/auth/verify",
            json={"email": "nobody@example.com", "code": requested.json()["debug_code"]},
        )

    assert verified.status_code == 404
    app.dependency_overrides.clear()


async def test_an_existing_account_can_become_a_worker(session: AsyncSession) -> None:
    session.add(User(email="grace@example.com", display_name="Grace"))
    await session.flush()

    async with client_for(session) as client:
        body = await sign_in(client, "grace@example.com", sign_up="worker")

    assert body["is_worker"] is True
    assert body["display_name"] == "Grace"
    app.dependency_overrides.clear()


async def test_claiming_an_invite_opens_a_guarantor_account(
    session: AsyncSession, worker: Worker
) -> None:
    from app.services import guarantor as guarantor_service

    agreement = await guarantor_service.invite_guarantor(
        session, worker, first_name="Hannah", last_name="Lazarus", relationship="employer"
    )
    await session.flush()

    async with client_for(session) as client:
        body = await sign_in(client, "hannah@example.com", sign_up="guarantor")
        assert body["is_worker"] is False

        claimed = await client.post(f"/api/v1/guarantor-instruments/{agreement.id}/claim")
        assert claimed.status_code == 200, claimed.text
        assert claimed.json()["claimed"] is True
        assert claimed.json()["guarantor"]["full_name"] == "Hannah Lazarus"

        me = (await client.get("/api/v1/auth/me")).json()
        assert me["is_guarantor"] is True
        assert me["display_name"] == "Hannah Lazarus"

    app.dependency_overrides.clear()


async def test_an_invite_cannot_be_claimed_signed_out(session: AsyncSession, worker: Worker) -> None:
    from app.services import guarantor as guarantor_service

    agreement = await guarantor_service.invite_guarantor(
        session, worker, first_name="Hannah", last_name="Lazarus", relationship="employer"
    )
    await session.flush()

    async with client_for(session) as client:
        unclaimed = await client.get(f"/api/v1/guarantor-instruments/{agreement.id}")
        assert unclaimed.json()["claimed"] is False
        assert unclaimed.json()["guarantor"]["full_name"] == "Hannah Lazarus"

        refused = await client.post(f"/api/v1/guarantor-instruments/{agreement.id}/claim")
        assert refused.status_code == 401

    app.dependency_overrides.clear()
