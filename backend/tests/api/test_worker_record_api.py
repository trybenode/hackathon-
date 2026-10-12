"""Purpose: Verify the worker's portable record route.

Dependencies: pytest, httpx ASGI transport, and the in-memory session fixture.
Used by: the backend test suite and CI.
"""

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.main import app
from app.models.domain import User, Worker


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


async def test_worker_reads_their_record(session: AsyncSession, worker: Worker) -> None:
    async with client_for(session) as client:
        assert (await client.get("/api/v1/me/record")).status_code == 401

        await sign_in(client, "worker@example.com")
        response = await client.get("/api/v1/me/record")

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["name"] == "Jane A."
        assert body["assessment"]["band"] == "Building History"
        assert body["outcomes"] == []
        assert body["credentials"] == {"identity": None, "guarantor": None, "imported_record": None}

    app.dependency_overrides.clear()


async def test_non_worker_has_no_record(session: AsyncSession) -> None:
    session.add(User(email="grace@example.com", display_name="Grace"))
    await session.flush()

    async with client_for(session) as client:
        await sign_in(client, "grace@example.com")
        assert (await client.get("/api/v1/me/record")).status_code == 404

    app.dependency_overrides.clear()


async def test_outcomes_page_through_every_completed_job(session: AsyncSession, worker: Worker) -> None:
    from tests.services.test_worker_record import add_outcome
    from app.models.domain import OutcomeSource

    source = OutcomeSource(name="seed", normalization_version="1")
    session.add(source)
    await session.flush()
    for index in range(23):
        await add_outcome(session, worker, source, days_ago=index)
    session.add(User(email="grace@example.com", display_name="Grace"))
    await session.flush()

    async with client_for(session) as client:
        assert (await client.get("/api/v1/me/record/outcomes")).status_code == 401
        await sign_in(client, "worker@example.com")
        record = (await client.get("/api/v1/me/record")).json()
        second = (await client.get("/api/v1/me/record/outcomes?page=2&size=20")).json()

        assert len(record["outcomes"]) == 20
        assert (second["total"], second["pages"], len(second["items"])) == (23, 2, 3)
        assert {"title", "rating", "client_name", "dispute"} <= set(second["items"][0])

    async with client_for(session) as client:
        await sign_in(client, "grace@example.com")
        assert (await client.get("/api/v1/me/record/outcomes")).status_code == 404

    app.dependency_overrides.clear()
