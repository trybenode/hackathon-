"""Purpose: Verify the guarantor endpoints cover create, sign, read, and refusals.

Dependencies: pytest, httpx ASGI transport, and the in-memory session fixture.
Used by: the backend test suite and CI.
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.main import app
from app.models.domain import Organization, OrganizationType, Worker
from app.models.portability import PlatformGrant, PlatformKey, WorkerLink
from app.services.portability import digest

#: The calling platform's key; the worker has approved it to read and write.
HEADERS: dict[str, str] = {}

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


LIVENESS_FRAME = {"frame": ("selfie.jpg", b"\xff\xd8" + b"x" * 512, "image/jpeg")}


async def pass_liveness(client: AsyncClient, instrument_id: str):
    await as_guarantor(client)
    return await client.post(
        f"/api/v1/guarantor-instruments/{instrument_id}/liveness", files=LIVENESS_FRAME
    )

IDENTITY_FORM = {
    "first_name": "Grace",
    "last_name": "Guarantor",
    "phone": "+2348012345678",
    "address": "12 Trust Street, Lagos",
    "nin": "12345678901",
    "bvn": "10987654321",
}


async def pass_identity(client: AsyncClient, instrument_id: str):
    """Submit the identity form the way the screen does, with a utility bill."""

    await as_guarantor(client)
    return await client.post(
        f"/api/v1/guarantor-instruments/{instrument_id}/identity",
        data=IDENTITY_FORM,
        files={"utility_bill": ("bill.pdf", b"%PDF-1.4 fake", "application/pdf")},
    )


async def platform(
    session: AsyncSession,
    worker: Worker | None,
    *,
    environment: str = "production",
    permissions: tuple[str, ...] = ("read_history", "import_history"),
) -> dict[str, str]:
    """A platform with a key, linked to the worker with the given approval."""

    org = Organization(name=f"Platform {uuid4().hex[:6]}", organization_type=OrganizationType.PLATFORM)
    session.add(org)
    await session.flush()
    secret = f"sk_test_{uuid4().hex}"
    session.add(PlatformKey(organization_id=org.id, key_hash=digest(secret), environment=environment))
    if worker is not None:
        grant = PlatformGrant(
            worker_id=worker.id, organization_id=org.id, token_hash=digest(uuid4().hex),
            permissions=list(permissions), expires_at=datetime.now(tz=UTC) + timedelta(days=7),
        )
        session.add(grant)
        await session.flush()
        session.add(WorkerLink(organization_id=org.id, worker_id=worker.id, external_worker_id="worker-1", grant_id=grant.id))
    await session.flush()
    return {"X-API-Key": secret}


@pytest_asyncio.fixture(autouse=True)
async def approved_platform(session: AsyncSession, worker: Worker) -> None:
    HEADERS.clear()
    HEADERS.update(await platform(session, worker))


def client_for(session: AsyncSession, headers: dict[str, str] | None = None) -> AsyncClient:
    async def _session_override():
        yield session

    app.dependency_overrides[get_db_session] = _session_override
    return AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", headers=HEADERS if headers is None else headers
    )


async def as_guarantor(client: AsyncClient, email: str = "grace@example.com") -> None:
    """Sign in as the guarantor, once per client, as the screens do before identity."""

    if (await client.get("/api/v1/auth/me")).status_code == 200:
        return
    code = (await client.post("/api/v1/auth/code", json={"email": email})).json()["debug_code"]
    verified = await client.post("/api/v1/auth/verify", json={"email": email, "code": code})
    assert verified.status_code == 200, verified.text


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
        assert signed.json()["status"] == "Pending Verification"

        identity = await pass_identity(client, instrument_id)
        assert identity.status_code == 200, identity.text
        body = identity.json()
        assert body["status"] == "verified"
        assert body["check_type"] == "identity"
        # The response must not echo the submitted identity numbers.
        assert "12345678901" not in identity.text
        assert "10987654321" not in identity.text

        verified = await pass_liveness(client, instrument_id)
        assert verified.status_code == 200, verified.text
        assert verified.json()["status"] == "Active"

        fetched = await client.get(f"/api/v1/guarantor-instruments/{instrument_id}")
        assert fetched.status_code == 200
        detail = fetched.json()
        assert detail["status"] == "Active"
        assert detail["guarantor"]["full_name"] == "Grace Guarantor"
        assert detail["guarantor"]["relationship"] == "sibling"

    app.dependency_overrides.clear()


async def test_response_carries_the_worker_card(session: AsyncSession, worker: Worker) -> None:
    async with client_for(session) as client:
        created = await client.post("/api/v1/guarantor-instruments", json=create_payload(worker))
        instrument_id = created.json()["instrument_id"]

        detail = (await client.get(f"/api/v1/guarantor-instruments/{instrument_id}")).json()

    assert detail["worker"] == {
        "worker_id": str(worker.id),
        "full_name": "Jane A.",
        "role": "Cleaner",
        "location": "Lekki, Lagos",
        "avatar_url": "https://example.com/jane.jpg",
        # No job is linked to this instrument.
        "job_title": None,
    }
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

        still_pending = await client.post(
            f"/api/v1/guarantor-instruments/{instrument_id}/trigger",
            json={"reason": "Not verified yet."},
        )
        assert still_pending.status_code == 409

        await pass_identity(client, instrument_id)
        await pass_liveness(client, instrument_id)
        triggered = await client.post(
            f"/api/v1/guarantor-instruments/{instrument_id}/trigger",
            json={"reason": "Client reported a no-show."},
        )
        assert triggered.status_code == 200
        assert triggered.json()["status"] == "Triggered"

    app.dependency_overrides.clear()


async def test_identity_rejects_malformed_numbers(
    session: AsyncSession, worker: Worker
) -> None:
    async with client_for(session) as client:
        created = await client.post("/api/v1/guarantor-instruments", json=create_payload(worker))
        instrument_id = created.json()["instrument_id"]
        await client.post(f"/api/v1/guarantor-instruments/{instrument_id}/sign", json=SIGN_PAYLOAD)
        await as_guarantor(client)

        response = await client.post(
            f"/api/v1/guarantor-instruments/{instrument_id}/identity",
            data={**IDENTITY_FORM, "nin": "123"},
        )
        assert response.status_code == 422

    app.dependency_overrides.clear()


async def test_liveness_without_identity_returns_409(
    session: AsyncSession, worker: Worker
) -> None:
    async with client_for(session) as client:
        created = await client.post("/api/v1/guarantor-instruments", json=create_payload(worker))
        instrument_id = created.json()["instrument_id"]
        await client.post(f"/api/v1/guarantor-instruments/{instrument_id}/sign", json=SIGN_PAYLOAD)

        response = await pass_liveness(client, instrument_id)
        assert response.status_code == 409

    app.dependency_overrides.clear()


async def test_liveness_rejects_an_empty_capture(
    session: AsyncSession, worker: Worker
) -> None:
    async with client_for(session) as client:
        created = await client.post("/api/v1/guarantor-instruments", json=create_payload(worker))
        instrument_id = created.json()["instrument_id"]
        await client.post(f"/api/v1/guarantor-instruments/{instrument_id}/sign", json=SIGN_PAYLOAD)
        await pass_identity(client, instrument_id)

        response = await client.post(
            f"/api/v1/guarantor-instruments/{instrument_id}/liveness",
            files={"frame": ("empty.jpg", b"", "image/jpeg")},
        )
        assert response.status_code == 422

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


async def test_expire_due_endpoint_closes_overdue_instruments(
    session: AsyncSession, worker: Worker
) -> None:
    from datetime import UTC, datetime, timedelta
    from uuid import UUID

    from sqlalchemy import select

    from app.models.domain import GuarantorAgreement

    async with client_for(session) as client:
        created = await client.post("/api/v1/guarantor-instruments", json=create_payload(worker))
        instrument_id = created.json()["instrument_id"]

        # Backdate it past its validity window.
        agreement = await session.scalar(
            select(GuarantorAgreement).where(GuarantorAgreement.id == UUID(instrument_id))
        )
        agreement.valid_until = datetime.now(tz=UTC) - timedelta(days=1)
        await session.flush()

        swept = await client.post("/api/v1/guarantor-instruments/expire-due")
        assert swept.status_code == 200
        assert swept.json() == {"expired": 1}

        detail = await client.get(f"/api/v1/guarantor-instruments/{instrument_id}")
        assert detail.json()["status"] == "Expired"

    app.dependency_overrides.clear()


async def test_unreachable_storage_returns_503(
    session: AsyncSession, worker: Worker, monkeypatch
) -> None:
    """A dropped connection to the bucket asks the guarantor to retry, not a 500."""

    from app.services import document_store as document_store_module
    from app.services.document_store import DocumentStorageError

    class Unreachable:
        name = "unreachable"

        async def store(self, *, filename: str, content: bytes, prefix: str):
            raise DocumentStorageError("We could not upload your document.")

    monkeypatch.setattr(document_store_module, "default_document_store", Unreachable())

    async with client_for(session) as client:
        created = await client.post("/api/v1/guarantor-instruments", json=create_payload(worker))
        instrument_id = created.json()["instrument_id"]
        await client.post(f"/api/v1/guarantor-instruments/{instrument_id}/sign", json=SIGN_PAYLOAD)

        response = await pass_identity(client, instrument_id)

        assert response.status_code == 503
        assert "Try again" in response.json()["detail"]
        # Still waiting on the checks, so the guarantor can resubmit.
        detail = (await client.get(f"/api/v1/guarantor-instruments/{instrument_id}")).json()
        assert detail["status"] == "Pending Verification"

    app.dependency_overrides.clear()


async def test_platform_endpoints_need_a_key(session: AsyncSession, worker: Worker) -> None:
    async with client_for(session, headers={}) as client:
        created = await client.post("/api/v1/guarantor-instruments", json=create_payload(worker))
        listed = await client.get("/api/v1/guarantor-instruments")

    assert created.status_code == 401
    assert listed.status_code == 401
    app.dependency_overrides.clear()


async def test_creating_needs_the_workers_approval_to_write(session: AsyncSession, worker: Worker) -> None:
    read_only = await platform(session, worker, permissions=("read_history",))
    stranger = await platform(session, None)
    async with client_for(session, headers=read_only) as client:
        refused = await client.post("/api/v1/guarantor-instruments", json=create_payload(worker))
    async with client_for(session, headers=stranger) as client:
        unlinked = await client.post("/api/v1/guarantor-instruments", json=create_payload(worker))
        listing = await client.get(f"/api/v1/guarantor-instruments?worker_id={worker.id}")

    assert refused.status_code == 403
    assert unlinked.status_code == 403
    assert listing.status_code == 403
    app.dependency_overrides.clear()


async def test_only_the_asking_platform_changes_a_guarantee(session: AsyncSession, worker: Worker) -> None:
    other = await platform(session, worker)
    async with client_for(session) as client:
        created = await client.post("/api/v1/guarantor-instruments", json=create_payload(worker))
        instrument_id = created.json()["instrument_id"]
    async with client_for(session, headers=other) as client:
        revoked = await client.post(
            f"/api/v1/guarantor-instruments/{instrument_id}/revoke", json={"reason": "Not ours"}
        )
        # Another approved platform can still see it on the worker.
        seen = await client.get(f"/api/v1/guarantor-instruments?worker_id={worker.id}")
        # But its own list holds only what it asked for.
        own = await client.get("/api/v1/guarantor-instruments")

    assert revoked.status_code == 403
    assert [item["instrument_id"] for item in seen.json()["items"]] == [instrument_id]
    assert own.json()["items"] == []
    app.dependency_overrides.clear()


async def test_identity_is_for_the_named_guarantor(session: AsyncSession, worker: Worker) -> None:
    from app.models.domain import User

    session.add(User(email="someone@example.com", display_name="Someone"))
    await session.flush()
    async with client_for(session) as client:
        created = await client.post("/api/v1/guarantor-instruments", json=create_payload(worker))
        instrument_id = created.json()["instrument_id"]
        await client.post(f"/api/v1/guarantor-instruments/{instrument_id}/sign", json=SIGN_PAYLOAD)
        signed_out = await client.post(f"/api/v1/guarantor-instruments/{instrument_id}/identity", data=IDENTITY_FORM)
        await as_guarantor(client, "someone@example.com")
        wrong_person = await client.post(f"/api/v1/guarantor-instruments/{instrument_id}/identity", data=IDENTITY_FORM)

    assert signed_out.status_code == 401
    assert wrong_person.status_code == 403
    app.dependency_overrides.clear()


async def test_sandbox_guarantees_are_answered_but_not_kept(session: AsyncSession, worker: Worker) -> None:
    from sqlalchemy import func, select

    from app.models.domain import GuarantorAgreement
    from app.services import sandbox

    workers = await sandbox.ensure_demo_workers(session)
    ada = workers["ada"]
    before = await session.scalar(select(func.count()).select_from(GuarantorAgreement))
    headers = await platform(session, ada, environment="sandbox")
    async with client_for(session, headers=headers) as client:
        created = await client.post("/api/v1/guarantor-instruments", json=create_payload(ada))
        listed = await client.get(f"/api/v1/guarantor-instruments?worker_id={ada.id}")

    assert created.status_code == 201, created.text
    assert await session.scalar(select(func.count()).select_from(GuarantorAgreement)) == before
    # Ada's demo guarantee is there to read.
    assert [item["status"] for item in listed.json()["items"]] == ["Active"]
    app.dependency_overrides.clear()


async def test_a_missing_key_is_refused_without_the_legacy_key(
    session: AsyncSession, worker: Worker, monkeypatch
) -> None:
    """CI runs without PLATFORM_API_KEY; a missing key is still the caller's 401."""

    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "platform_api_key", "")
    async with client_for(session, headers={}) as client:
        missing = await client.get("/api/v1/guarantor-instruments")
        wrong = await client.get("/api/v1/guarantor-instruments", headers={"X-API-Key": "sk_wrong"})

    assert (missing.status_code, wrong.status_code) == (401, 401)
    app.dependency_overrides.clear()
