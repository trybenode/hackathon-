"""Purpose: Verify the guarantee details and agreement download routes.

Dependencies: pytest, httpx ASGI transport, and the in-memory session fixture.
Used by: the backend test suite and CI.
"""

from datetime import UTC, datetime, timedelta

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.main import app
from app.models.domain import AgreementStatus, GuarantorAgreement, User, Worker

NOW = datetime.now(tz=UTC)


def client_for(session: AsyncSession) -> AsyncClient:
    async def _session_override():
        yield session

    app.dependency_overrides[get_db_session] = _session_override
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def sign_in(client: AsyncClient, email: str) -> None:
    requested = await client.post("/api/v1/auth/code", json={"email": email})
    verified = await client.post(
        "/api/v1/auth/verify", json={"email": email, "code": requested.json()["debug_code"]}
    )
    assert verified.status_code == 200, verified.text


async def guarantee_for(session: AsyncSession, worker: Worker, guarantor: User) -> GuarantorAgreement:
    agreement = GuarantorAgreement(
        worker_id=worker.id,
        guarantor_user_id=guarantor.id,
        scope="Domestic cleaning",
        conditions="Covers no-show.",
        relationship_type="employer",
        status=AgreementStatus.ACTIVE,
        signed_at=NOW,
        verified_at=NOW,
        valid_until=NOW + timedelta(days=365),
    )
    session.add(agreement)
    await session.flush()
    return agreement


async def test_guarantee_detail_and_agreement(session: AsyncSession, worker: Worker) -> None:
    guarantor = User(email="grace@example.com", display_name="Grace Guarantor")
    session.add(guarantor)
    await session.flush()
    agreement = await guarantee_for(session, worker, guarantor)

    async with client_for(session) as client:
        await sign_in(client, "grace@example.com")

        detail = await client.get(f"/api/v1/me/guarantees/{agreement.id}")
        assert detail.status_code == 200, detail.text
        body = detail.json()
        assert body["guarantee"]["bucket"] == "active"
        assert body["guarantee"]["reference"].startswith("G-")
        assert body["relationship"] == "employer"
        assert body["agreement"]

        download = await client.get(f"/api/v1/me/guarantees/{agreement.id}/agreement")
        assert download.status_code == 200
        assert "attachment" in download.headers["content-disposition"]
        assert "Domestic cleaning" in download.text

    app.dependency_overrides.clear()


async def test_someone_elses_guarantee_is_not_found(session: AsyncSession, worker: Worker) -> None:
    owner = User(email="owner@example.com", display_name="Owner")
    other = User(email="other@example.com", display_name="Other")
    session.add_all([owner, other])
    await session.flush()
    agreement = await guarantee_for(session, worker, owner)

    async with client_for(session) as client:
        await sign_in(client, "other@example.com")

        assert (await client.get(f"/api/v1/me/guarantees/{agreement.id}")).status_code == 404
        assert (
            await client.get(f"/api/v1/me/guarantees/{agreement.id}/agreement")
        ).status_code == 404

    app.dependency_overrides.clear()
