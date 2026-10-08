"""Purpose: Verify the escrow routes for platforms, workers and Payscrow's webhook.

Dependencies: pytest, httpx ASGI transport, and the in-memory session fixture.
Used by: the backend test suite and CI. Uses the stub provider throughout.
"""

import json

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_db_session
from app.main import app
from app.models.domain import Worker
from app.services.escrow_provider import sign_webhook

PLATFORM = {"X-API-Key": "test-platform-key"}


@pytest.fixture(autouse=True)
def keys(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "platform_api_key", "test-platform-key")
    monkeypatch.setattr(get_settings(), "payscrow_webhook_secret", "test-webhook-secret")


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


def job_payload(worker: Worker) -> dict:
    return {
        "worker_id": str(worker.id),
        "title": "Home cleaning",
        "amount": "25000.00",
        "client_name": "Peter James",
        "client_email": "peter@example.com",
        "client_phone": "08012345678",
        "location": "Lekki, Lagos",
        "details": [{"label": "Bedrooms", "value": "2"}],
    }


async def deliver(client: AsyncClient, payload: dict, *, secret: str = "test-webhook-secret"):
    body = json.dumps(payload).encode()
    headers = {"Content-Type": "application/json", **sign_webhook(secret, body)}
    return await client.post("/api/v1/webhooks/payscrow", content=body, headers=headers)


async def test_full_escrow_flow_over_http(session: AsyncSession, worker: Worker) -> None:
    async with client_for(session) as client:
        assert (await client.post("/api/v1/jobs", json=job_payload(worker))).status_code == 401

        created = await client.post("/api/v1/jobs", json=job_payload(worker), headers=PLATFORM)
        assert created.status_code == 201, created.text
        job_id = created.json()["job_id"]
        number = created.json()["transaction_number"]
        assert created.json()["payment_link"]

        # An unsigned webhook is refused; a signed one funds the escrow.
        forged = await client.post(
            "/api/v1/webhooks/payscrow", json={"transactionNumber": number, "paymentStatus": "Paid"}
        )
        assert forged.status_code == 401
        funded = await deliver(
            client,
            {
                "transactionId": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                "transactionNumber": number,
                "paymentStatus": "Paid",
                "escrowCode": "ABC123DEF4",
            },
        )
        assert funded.json() == {"status": "funded"}

        await sign_in(client, "worker@example.com")
        jobs = (await client.get("/api/v1/me/jobs")).json()
        assert [job["stage"] for job in jobs] == ["held"]
        assert jobs[0]["escrow"]["code_on_file"] is True
        # The code itself is never sent to the screens.
        assert "ABC123DEF4" not in json.dumps(jobs)

        completed = await client.post(f"/api/v1/me/jobs/{job_id}/complete")
        assert completed.json()["stage"] == "awaiting_confirmation"

        confirmed = await client.post(
            f"/api/v1/jobs/{job_id}/client-confirmation", json={}, headers=PLATFORM
        )
        assert confirmed.status_code == 200, confirmed.text
        assert confirmed.json()["stage"] == "released"

    app.dependency_overrides.clear()


async def test_worker_reports_an_issue(session: AsyncSession, worker: Worker) -> None:
    async with client_for(session) as client:
        created = (await client.post("/api/v1/jobs", json=job_payload(worker), headers=PLATFORM)).json()
        await deliver(
            client,
            {"transactionId": "id-1", "transactionNumber": created["transaction_number"], "paymentStatus": "Paid"},
        )
        await sign_in(client, "worker@example.com")

        reported = await client.post(
            f"/api/v1/me/jobs/{created['job_id']}/issue",
            json={"reason": "Work conditions changed", "complaint": "Two extra rooms"},
        )
        assert reported.status_code == 200, reported.text
        assert reported.json()["stage"] == "disputed"
        assert reported.json()["dispute"]["reference"].startswith("D-")

        # No code on file and disputed: confirming cannot release.
        refused = await client.post(
            f"/api/v1/jobs/{created['job_id']}/client-confirmation", json={}, headers=PLATFORM
        )
        assert refused.status_code == 409

    app.dependency_overrides.clear()


async def test_confirming_without_a_code_explains_why(session: AsyncSession, worker: Worker) -> None:
    async with client_for(session) as client:
        created = (await client.post("/api/v1/jobs", json=job_payload(worker), headers=PLATFORM)).json()
        await deliver(
            client,
            {"transactionId": "id-2", "transactionNumber": created["transaction_number"], "paymentStatus": "Paid"},
        )

        refused = await client.post(
            f"/api/v1/jobs/{created['job_id']}/client-confirmation", json={}, headers=PLATFORM
        )
        assert refused.status_code == 409
        assert "escrow code" in refused.json()["detail"]

        await sign_in(client, "worker@example.com")
        code = await client.post(
            f"/api/v1/me/jobs/{created['job_id']}/escrow-code", json={"code": "XYZ789ABC1"}
        )
        assert code.status_code == 204
        released = await client.post(
            f"/api/v1/jobs/{created['job_id']}/client-confirmation", json={}, headers=PLATFORM
        )
        assert released.json()["stage"] == "released"

    app.dependency_overrides.clear()
