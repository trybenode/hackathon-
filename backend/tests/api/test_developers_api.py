"""Purpose: Verify the developer journey over HTTP, from sign-up to a first sandbox call.

Dependencies: pytest, httpx ASGI transport, and the in-memory session fixture.
Used by: the backend test suite and CI.
"""

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.models.domain import User
from app.services import developers, sandbox
from tests.api.test_auth_api import client_for

PDF = ("doc.pdf", b"%PDF-1.4 doc", "application/pdf")
BUSINESS = {
    "business_name": "Energies Technologies Ltd.",
    "business_type": "limited_liability_company",
    "registration_number": "RC1234567",
    "tax_id": "12345678-0001",
    "confirmed": "true",
}


async def sign_up(client: AsyncClient) -> None:
    code = (await client.post("/api/v1/auth/code", json={"email": "alex@company.com"})).json()["debug_code"]
    verified = await client.post(
        "/api/v1/auth/verify", json={"email": "alex@company.com", "code": code, "sign_up": "developer"}
    )
    assert verified.status_code == 200, verified.text


async def verify(client: AsyncClient) -> dict:
    identity = await client.post(
        "/api/v1/me/developer/identity",
        data={"full_name": "Alex Daniel Morgan", "document_type": "international_passport"},
        files={"document": PDF},
    )
    assert identity.status_code == 200, identity.text
    business = await client.post("/api/v1/me/developer/business", data=BUSINESS, files={"document": PDF})
    assert business.status_code == 200, business.text
    return business.json()


async def approve(session: AsyncSession) -> None:
    user = await session.scalar(select(User).where(User.email == "alex@company.com"))
    account = await developers.account_for(session, user)
    await developers.approve(session, account)
    await session.commit()


async def test_a_new_developer_starts_unverified(session: AsyncSession) -> None:
    async with client_for(session) as client:
        await sign_up(client)
        dashboard = (await client.get("/api/v1/me/developer")).json()

    assert dashboard["kyb_status"] == "not_started"
    assert dashboard["identity_submitted"] is False
    assert (dashboard["usage"]["total_calls"], dashboard["usage"]["successful_calls"]) == (0, 0)
    assert len(dashboard["usage"]["daily"]) == 14
    assert len(dashboard["sandbox_workers"]) == 4
    app.dependency_overrides.clear()


async def test_submitting_both_steps_waits_for_review(session: AsyncSession) -> None:
    async with client_for(session) as client:
        await sign_up(client)
        dashboard = await verify(client)
        early = await client.post("/api/v1/me/developer/keys", json={"name": "Server", "environment": "sandbox"})

    assert (dashboard["kyc_status"], dashboard["kyb_status"]) == ("under_review", "under_review")
    assert early.status_code == 409
    app.dependency_overrides.clear()


async def test_the_business_step_needs_the_confirmation(session: AsyncSession) -> None:
    async with client_for(session) as client:
        await sign_up(client)
        await client.post(
            "/api/v1/me/developer/identity",
            data={"full_name": "Alex Morgan", "document_type": "national_id"}, files={"document": PDF},
        )
        refused = await client.post(
            "/api/v1/me/developer/business", data={**BUSINESS, "confirmed": "false"}, files={"document": PDF}
        )

    assert refused.status_code == 422
    app.dependency_overrides.clear()


async def test_approved_developer_calls_the_api_with_a_sandbox_key(session: AsyncSession) -> None:
    async with client_for(session) as client:
        await sign_up(client)
        await verify(client)
        await approve(session)

        generated = await client.post("/api/v1/me/developer/keys", json={"name": "Server", "environment": "sandbox"})
        assert generated.status_code == 201, generated.text
        secret = generated.json()["secret"]

        linked = await client.post(
            "/api/v1/platform/worker-links",
            headers={"X-API-Key": secret},
            json={"external_worker_id": "user-42", "consent_token": sandbox.DEMO_WORKERS[1].consent_token},
        )
        assert linked.status_code == 201, linked.text

        dashboard = (await client.get("/api/v1/me/developer")).json()

    assert dashboard["kyb_status"] == "approved"
    assert dashboard["credentials"][0]["key_id"] == generated.json()["key"]["key_id"]
    assert (dashboard["usage"]["total_calls"], dashboard["usage"]["successful_calls"]) == (1, 1)
    assert dashboard["usage"]["daily"][-1] == {"day": dashboard["usage"]["daily"][-1]["day"], "total": 1, "successful": 1}
    assert dashboard["recent_activity"][0]["path"] == "/api/v1/platform/worker-links"
    app.dependency_overrides.clear()


async def test_a_name_change_waits_for_review(session: AsyncSession) -> None:
    async with client_for(session) as client:
        await sign_up(client)
        await verify(client)
        await approve(session)
        requested = await client.post(
            "/api/v1/me/developer/name-change", data={"new_name": "Alex D. Morgan", "reason": "correction"}
        )

    assert requested.status_code == 200, requested.text
    assert requested.json()["name_change"] == {"new_name": "Alex D. Morgan", "status": "under_review"}
    assert requested.json()["full_name"] == "Alex Daniel Morgan"
    app.dependency_overrides.clear()


async def test_the_dashboard_is_for_developers(session: AsyncSession) -> None:
    session.add(User(email="grace@example.com", display_name="Grace"))
    await session.flush()
    async with client_for(session) as client:
        signed_out = await client.get("/api/v1/me/developer")
        code = (await client.post("/api/v1/auth/code", json={"email": "grace@example.com"})).json()["debug_code"]
        await client.post("/api/v1/auth/verify", json={"email": "grace@example.com", "code": code})
        not_developer = await client.get("/api/v1/me/developer")

    assert signed_out.status_code == 401
    assert not_developer.status_code == 404
    app.dependency_overrides.clear()


async def test_managing_an_api_key(session: AsyncSession) -> None:
    async with client_for(session) as client:
        await sign_up(client)
        await verify(client)
        await approve(session)

        created = await client.post(
            "/api/v1/me/developer/keys", json={"name": "Checkout", "environment": "sandbox", "scopes": ["history"]}
        )
        assert created.status_code == 201, created.text
        key, secret = created.json()["key"], created.json()["secret"]
        assert (key["name"], key["scopes"], key["environment"]) == ("Checkout", ["history"], "sandbox")

        listed = (await client.get("/api/v1/me/developer/keys")).json()
        assert [item["id"] for item in listed["items"]] == [key["id"]]
        assert "secret" not in listed["items"][0]
        assert [group["id"] for group in listed["access_groups"]] == ["trust", "history", "guarantees", "scoring"]
        assert listed["max_active_per_environment"] == 5

        # History only: linking a worker is Trust & workers access.
        link = {"external_worker_id": "user-1", "consent_token": sandbox.DEMO_WORKERS[0].consent_token}
        refused = await client.post("/api/v1/platform/worker-links", headers={"X-API-Key": secret}, json=link)
        assert refused.json()["code"] == "SCOPE_REQUIRED"

        widened = await client.patch(f"/api/v1/me/developer/keys/{key['id']}", json={"name": "Checkout", "scopes": None})
        assert widened.json()["scopes"] is None
        allowed = await client.post("/api/v1/platform/worker-links", headers={"X-API-Key": secret}, json=link)
        assert allowed.status_code == 201

        rotated = await client.post(f"/api/v1/me/developer/keys/{key['id']}/rotate")
        new_secret = rotated.json()["secret"]
        assert rotated.json()["key"]["key_id"] == key["key_id"]
        old = await client.get("/api/v1/platform/scoring-config", headers={"X-API-Key": secret})
        new = await client.get("/api/v1/platform/scoring-config", headers={"X-API-Key": new_secret})
        assert (old.status_code, new.status_code) == (401, 200)

        revoked = await client.delete(f"/api/v1/me/developer/keys/{key['id']}")
        assert revoked.status_code == 204
        assert (await client.get("/api/v1/me/developer/keys")).json()["items"] == []
        gone = await client.get("/api/v1/platform/scoring-config", headers={"X-API-Key": new_secret})
        assert gone.status_code == 401

    app.dependency_overrides.clear()
