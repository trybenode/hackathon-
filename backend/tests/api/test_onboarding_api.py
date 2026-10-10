"""Purpose: Verify the worker onboarding endpoints from sign-up to guarantor link.

Dependencies: pytest, httpx ASGI transport, and the in-memory session fixture.
Used by: the backend test suite and CI.
"""

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from tests.api.test_auth_api import client_for, sign_in

IDENTITY = {
    "first_name": "Jane",
    "last_name": "Adams",
    "date_of_birth": "1995-04-02",
    "phone": "+2348012345678",
    "address": "12 Trust Street, Lagos",
    "nin": "12345678901",
    "bvn": "10987654321",
}
FRAME = ("selfie.jpg", b"\xff\xd8" + b"x" * 512, "image/jpeg")


async def signed_up(client: AsyncClient) -> None:
    await sign_in(client, "jane@example.com", sign_up="worker")


async def test_onboarding_runs_identity_then_liveness_then_guarantor(session: AsyncSession) -> None:
    async with client_for(session) as client:
        await signed_up(client)
        assert (await client.get("/api/v1/me/worker/onboarding")).json()["next_step"] == "identity"

        identity = await client.post(
            "/api/v1/me/worker/identity",
            data=IDENTITY,
            files={"utility_bill": ("bill.pdf", b"%PDF-1.4 bill", "application/pdf")},
        )
        assert identity.status_code == 200, identity.text
        assert identity.json()["next_step"] == "liveness"

        liveness = await client.post("/api/v1/me/worker/liveness", files={"frame": FRAME})
        assert liveness.status_code == 200, liveness.text
        assert liveness.json()["next_step"] == "guarantor"

        invite = await client.post(
            "/api/v1/me/worker/guarantor",
            json={"first_name": "Hannah", "last_name": "Lazarus", "relationship": "employer"},
        )
        assert invite.status_code == 201, invite.text
        body = invite.json()
        assert body["name"] == "Hannah Lazarus"
        assert body["status"] == "Pending Signature"
        assert body["link"].endswith(f"/guarantor/{body['instrument_id']}/review")

        progress = (await client.get("/api/v1/me/worker/onboarding")).json()
        assert progress["guarantor"] == "pending"
        assert progress["next_step"] is None
        assert progress["invite"]["instrument_id"] == body["instrument_id"]

        me = (await client.get("/api/v1/auth/me")).json()
        assert me["display_name"] == "Jane Adams"
        assert me["onboarding_step"] is None

    app.dependency_overrides.clear()


async def test_bad_identity_numbers_are_refused(session: AsyncSession) -> None:
    async with client_for(session) as client:
        await signed_up(client)
        refused = await client.post("/api/v1/me/worker/identity", data={**IDENTITY, "nin": "123"})

        assert refused.status_code == 422
        assert (await client.get("/api/v1/me/worker/onboarding")).json()["next_step"] == "identity"

    app.dependency_overrides.clear()


async def test_steps_cannot_be_skipped(session: AsyncSession) -> None:
    async with client_for(session) as client:
        await signed_up(client)

        liveness = await client.post("/api/v1/me/worker/liveness", files={"frame": FRAME})
        invite = await client.post(
            "/api/v1/me/worker/guarantor",
            json={"first_name": "Hannah", "last_name": "Lazarus", "relationship": "employer"},
        )

    assert liveness.status_code == 409
    assert invite.status_code == 409
    app.dependency_overrides.clear()


async def test_onboarding_needs_a_worker_session(session: AsyncSession) -> None:
    async with client_for(session) as client:
        signed_out = await client.get("/api/v1/me/worker/onboarding")
        await sign_in(client, "hannah@example.com", sign_up="guarantor")
        not_a_worker = await client.get("/api/v1/me/worker/onboarding")

    assert signed_out.status_code == 401
    assert not_a_worker.status_code == 404
    app.dependency_overrides.clear()
