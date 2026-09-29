"""Purpose: Verify the guarantor endpoints cover create, sign, read, and refusals.

Dependencies: pytest, httpx ASGI transport, and the in-memory session fixture.
Used by: the backend test suite and CI.
"""

from datetime import UTC, datetime, timedelta

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.main import app
from app.models.domain import Worker

NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


def create_payload(worker: Worker, **overrides: object) -> dict:
    payload = {
        "worker_id": str(worker.id),
        "guarantor": {
            "full_name": "Grace Guarantor",
            "phone": "+2348012345678",
            "email": "grace@example.com",
            "relationship": "sibling",
            "address": "12 Trust Street, Lagos",
        },
        "scope": "Domestic cleaning jobs up to NGN 50,000",
        "conditions": "Covers no-show and property damage claims.",
        "valid_until": (datetime.now(tz=UTC) + timedelta(days=30)).isoformat(),
    }
    payload.update(overrides)
    return payload


SIGN_PAYLOAD = {
    "signer_name": "Grace Guarantor",
    "signer_phone": "+2348012345678",
    "accepted": True,
    "signature_metadata": {
        "ip": "102.89.1.7",
        "user_agent": "Mozilla/5.0 (iPhone)",
        "timestamp": datetime.now(tz=UTC).isoformat(),
    },
}


def client_for(session: AsyncSession) -> AsyncClient:
    async def _session_override():
        yield session

    app.dependency_overrides[get_db_session] = _session_override
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def test_create_sign_and_fetch(session: AsyncSession, worker: Worker) -> None:
    async with client_for(session) as client:
        created = await client.post("/api/v1/guarantor-instruments", json=create_payload(worker))
        assert created.status_code == 201, created.text
        body = created.json()
        assert body["status"] == "Pending Signature"
        instrument_id = body["instrument_id"]

        signed = await client.post(
            f"/api/v1/guarantor-instruments/{instrument_id}/sign", json=SIGN_PAYLOAD
        )
        assert signed.status_code == 200, signed.text
        assert signed.json()["status"] == "Active"

        fetched = await client.get(f"/api/v1/guarantor-instruments/{instrument_id}")
        assert fetched.status_code == 200
        detail = fetched.json()
        assert detail["status"] == "Active"
        assert detail["guarantor"]["full_name"] == "Grace Guarantor"
        assert detail["guarantor"]["relationship"] == "sibling"

    app.dependency_overrides.clear()


async def test_draft_flow_and_listing(session: AsyncSession, worker: Worker) -> None:
    async with client_for(session) as client:
        created = await client.post(
            "/api/v1/guarantor-instruments", json=create_payload(worker, as_draft=True)
        )
        instrument_id = created.json()["instrument_id"]
        assert created.json()["status"] == "Draft"

        sent = await client.post(f"/api/v1/guarantor-instruments/{instrument_id}/send")
        assert sent.status_code == 200
        assert sent.json()["status"] == "Pending Signature"

        listed = await client.get(
            "/api/v1/guarantor-instruments", params={"worker_id": str(worker.id)}
        )
        assert [item["instrument_id"] for item in listed.json()["items"]] == [instrument_id]

    app.dependency_overrides.clear()


async def test_trigger_requires_active_instrument(session: AsyncSession, worker: Worker) -> None:
    async with client_for(session) as client:
        created = await client.post("/api/v1/guarantor-instruments", json=create_payload(worker))
        instrument_id = created.json()["instrument_id"]

        too_early = await client.post(
            f"/api/v1/guarantor-instruments/{instrument_id}/trigger",
            json={"reason": "Client reported a no-show."},
        )
        assert too_early.status_code == 409

        await client.post(f"/api/v1/guarantor-instruments/{instrument_id}/sign", json=SIGN_PAYLOAD)
        triggered = await client.post(
            f"/api/v1/guarantor-instruments/{instrument_id}/trigger",
            json={"reason": "Client reported a no-show."},
        )
        assert triggered.status_code == 200
        assert triggered.json()["status"] == "Triggered"

    app.dependency_overrides.clear()


async def test_unknown_instrument_returns_404(session: AsyncSession, worker: Worker) -> None:
    async with client_for(session) as client:
        response = await client.get(f"/api/v1/guarantor-instruments/{worker.id}")
        assert response.status_code == 404

    app.dependency_overrides.clear()


async def test_self_guarantee_returns_422(session: AsyncSession, worker: Worker) -> None:
    payload = create_payload(worker)
    payload["guarantor"]["email"] = "worker@example.com"

    async with client_for(session) as client:
        response = await client.post("/api/v1/guarantor-instruments", json=payload)
        assert response.status_code == 422

    app.dependency_overrides.clear()
