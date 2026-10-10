"""Purpose: Verify the job routes for workers, customers (by link) and Payscrow.

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


@pytest.fixture(autouse=True)
def secret(monkeypatch: pytest.MonkeyPatch) -> None:
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


async def deliver(client: AsyncClient, payload: dict, *, secret: str = "test-webhook-secret"):
    body = json.dumps(payload).encode()
    headers = {"Content-Type": "application/json", **sign_webhook(secret, body)}
    return await client.post("/api/v1/webhooks/payscrow", content=body, headers=headers)


async def create_link(client: AsyncClient) -> dict:
    created = await client.post(
        "/api/v1/me/jobs",
        json={
            "title": "Home cleaning",
            "address": "Lagos Island, Lagos",
            "scheduled_at": "2026-11-20T12:00:00+01:00",
            "price": "25000.00",
        },
    )
    assert created.status_code == 201, created.text
    return created.json()


async def pay(client: AsyncClient, token: str) -> dict:
    paying = await client.post(
        f"/api/v1/public/jobs/{token}/payment",
        json={"name": "Sarah Ade", "email": "sarah@example.com", "phone": "08012345678"},
    )
    assert paying.status_code == 200, paying.text
    return paying.json()


async def test_full_job_flow_over_http(session: AsyncSession, worker: Worker) -> None:
    async with client_for(session) as client:
        assert (await client.post("/api/v1/me/jobs", json={})).status_code == 401
        await sign_in(client, "worker@example.com")

        job = await create_link(client)
        assert job["stage"] == "awaiting_customer"
        token = job["link"].rsplit("/j/", 1)[1]

        # The customer opens the link: no account needed.
        public = (await client.get(f"/api/v1/public/jobs/{token}")).json()
        assert public["worker"]["name"] == "Jane A."
        assert public["worker"]["band"] == "Building History"
        assert public["premium"] == "500.00"
        assert public["stage"] == "awaiting_customer"

        payment = await pay(client, token)
        assert payment["payment_link"]
        assert payment["total_payable"] == "25500.00"

        # The worker sees customer details only once they have paid.
        mine = (await client.get(f"/api/v1/me/jobs/{job['id']}")).json()
        assert mine["client_name"] is None

        number = mine["transaction_number"]
        forged = await client.post(
            "/api/v1/webhooks/payscrow", json={"transactionNumber": number, "paymentStatus": "Paid"}
        )
        assert forged.status_code == 401
        funded = await deliver(
            client, {"transactionId": "guid-1", "transactionNumber": number, "paymentStatus": "Paid"}
        )
        assert funded.json() == {"status": "funded"}

        mine = (await client.get(f"/api/v1/me/jobs/{job['id']}")).json()
        assert mine["stage"] == "held" and mine["client_name"] == "Sarah Ade"

        completed = await client.post(f"/api/v1/me/jobs/{job['id']}/complete")
        assert completed.json()["stage"] == "awaiting_confirmation"
        public = (await client.get(f"/api/v1/public/jobs/{token}")).json()
        assert public["confirm_by"] is not None

        missing_rating = await client.post(
            f"/api/v1/public/jobs/{token}/release", json={"code": "XYZ789ABC1"}
        )
        assert missing_rating.status_code == 422
        released = await client.post(
            f"/api/v1/public/jobs/{token}/release", json={"code": "XYZ789ABC1", "rating": 5}
        )
        assert released.status_code == 200, released.text
        assert released.json()["stage"] == "released"
        assert released.json()["rating"] == 5

    app.dependency_overrides.clear()


async def test_customer_reports_a_problem_with_evidence(session: AsyncSession, worker: Worker) -> None:
    async with client_for(session) as client:
        await sign_in(client, "worker@example.com")
        job = await create_link(client)
        token = job["link"].rsplit("/j/", 1)[1]
        await pay(client, token)
        number = (await client.get(f"/api/v1/me/jobs/{job['id']}")).json()["transaction_number"]
        await deliver(client, {"transactionId": "g", "transactionNumber": number, "paymentStatus": "Paid"})

        reported = await client.post(
            f"/api/v1/public/jobs/{token}/issue",
            data={"reason": "Damaged or missing items", "complaint": "The vase broke"},
            files=[("evidence", ("photo.jpg", b"\xff\xd8\xff fake", "image/jpeg"))],
        )
        assert reported.status_code == 200, reported.text
        body = reported.json()
        assert body["stage"] == "disputed"
        assert body["dispute"]["raised_by"] == "customer"
        assert body["dispute"]["history"][0]["stage"] == "NegotiationOpen"

        # The worker sees the same dispute.
        mine = (await client.get(f"/api/v1/me/jobs/{job['id']}")).json()
        assert mine["dispute"]["reason"] == "Damaged or missing items"

    app.dependency_overrides.clear()


async def test_worker_reports_an_issue(session: AsyncSession, worker: Worker) -> None:
    async with client_for(session) as client:
        await sign_in(client, "worker@example.com")
        job = await create_link(client)
        token = job["link"].rsplit("/j/", 1)[1]
        await pay(client, token)
        number = (await client.get(f"/api/v1/me/jobs/{job['id']}")).json()["transaction_number"]
        await deliver(client, {"transactionId": "g", "transactionNumber": number, "paymentStatus": "Paid"})

        reported = await client.post(
            f"/api/v1/me/jobs/{job['id']}/issue",
            data={"reason": "Work conditions changed", "complaint": "Two extra rooms"},
        )
        assert reported.status_code == 200, reported.text
        assert reported.json()["dispute"]["raised_by"] == "worker"

    app.dependency_overrides.clear()


async def test_bad_link_is_not_found(session: AsyncSession) -> None:
    async with client_for(session) as client:
        assert (await client.get("/api/v1/public/jobs/not-a-token")).status_code == 404

    app.dependency_overrides.clear()
