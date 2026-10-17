"""HTTP import receipts, private attachment access, additive contracts and origin enforcement."""

from uuid import uuid4
import pytest
from httpx import ASGITransport, AsyncClient
from app.api.v1.endpoints.auth import current_user
from app.api.v1.endpoints.admission import guard
from app.core.config import get_settings
from app.db.session import get_db_session
from app.main import app
from app.models.domain import User
from app.models.admission import ReviewMembership


@pytest.fixture
async def client(session, worker, monkeypatch, tmp_path):
    cfg = get_settings()
    monkeypatch.setattr(cfg, "environment", "development")
    monkeypatch.setattr(cfg, "unsigned_imports_enabled", True)
    monkeypatch.setattr(cfg, "additional_verification_enabled", True)
    monkeypatch.setattr(cfg, "s3_bucket", "")
    monkeypatch.setattr(cfg, "ownership_storage_dir", str(tmp_path))
    actor = {"id": worker.user_id}

    async def user():
        return await session.get(User, actor["id"])

    async def db():
        try:
            yield session
        except Exception:
            await session.rollback()
            raise

    async def no_limit():
        pass

    app.dependency_overrides.update(
        {current_user: user, get_db_session: db, guard: no_limit}
    )
    await session.commit()
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as api:
            yield api, actor
    finally:
        app.dependency_overrides.clear()


async def test_csv_document_and_receipt_recovery(client, worker):
    api, _ = client
    operation = str(uuid4())
    data = f"worker_id,job_id,date,status\n{worker.id},a-job,2025-01-01,completed\n"
    result = await api.post(
        "/api/v1/me/history-imports",
        headers={"Idempotency-Key": operation},
        data={"source_name": "Old invoices"},
        files={"csv_file": ("jobs.csv", data, "text/csv")},
    )
    assert result.status_code == 201, result.text
    batch = result.json()
    receipt = await api.get(f"/api/v1/me/history-imports/operations/{operation}")
    assert receipt.json()["id"] == batch["id"]
    attachment = await api.put(
        f"/api/v1/me/history-imports/{batch['id']}/document",
        files={"document": ("job.pdf", b"%PDF-1.4\nprivate\n%%EOF", "application/pdf")},
    )
    assert attachment.status_code == 200, attachment.text
    submission = await api.post(
        f"/api/v1/me/history-imports/{batch['id']}/submit",
        json={"version": attachment.json()["version"]},
    )
    assert submission.json()["state"] == "submitted"
    repeated = await api.post(
        f"/api/v1/me/history-imports/{batch['id']}/submit",
        json={"version": attachment.json()["version"]},
    )
    assert repeated.status_code == 200
    record = await api.get("/api/v1/me/record")
    assert record.status_code == 200, record.text
    assert record.json()["onboarding"]["action"] == "additional_verification"
    assert record.json()["provisional_history"]["rating"] is None
    listed = await api.get("/api/v1/me/history-imports")
    assert listed.json()["items"][0]["rows"] == []
    assert "document_key" not in listed.text
    denied = await api.get(f"/api/v1/review/imports/{batch['id']}/document")
    assert denied.status_code == 403


async def test_wrong_worker_and_missing_consent_cannot_be_bypassed(client, worker):
    api, _ = client
    response = await api.post(
        "/api/v1/me/history-imports",
        headers={"Idempotency-Key": str(uuid4())},
        data={"source_name": "Old invoices"},
        files={
            "csv_file": (
                "jobs.csv",
                f"worker_id,job_id,date,status\n{uuid4()},a,2025-01-01,completed\n",
                "text/csv",
            )
        },
    )
    assert response.status_code == 422 and response.json()["code"] == "WORKER_MISMATCH"
    case = await api.post(
        "/api/v1/me/additional-verification/cases",
        json={"organization_id": str(uuid4())},
    )
    # Tenant opt-in/consent is never inferred from an arbitrary UUID.
    assert case.status_code in (403, 409)


async def test_bad_credential_never_becomes_unsigned(client):
    api, _ = client
    response = await api.post(
        "/api/v1/me/history-imports",
        headers={"Idempotency-Key": str(uuid4())},
        data={"source_name": "Claimed signed"},
        files={
            "csv_file": (
                "credential.json",
                '{"credential_token":"tampered"}',
                "application/json",
            )
        },
    )
    assert (
        response.status_code == 422
        and response.json()["code"] == "SIGNED_ROUTE_REQUIRED"
    )


async def test_feature_flag_and_role_isolation(client, session):
    api, actor = client
    get_settings().unsigned_imports_enabled = False
    response = await api.get("/api/v1/me/history-imports")
    assert response.status_code == 404
    get_settings().unsigned_imports_enabled = True
    stranger = User(email="review-stranger@example.com", display_name="Stranger")
    session.add(stranger)
    await session.commit()
    actor["id"] = stranger.id
    response = await api.get("/api/v1/review/imports")
    assert response.status_code == 403


async def test_private_attachment_is_never_inline(client, session, worker):
    from app.services import ownership_imports

    api, actor = client
    owner = await session.get(User, worker.user_id)
    row = await ownership_imports.prepare(
        session,
        owner,
        f"worker_id,job_id,date,status\n{worker.id},job-a,2025-01-01,completed\n".encode(),
        "Source",
        uuid4(),
    )
    row = await ownership_imports.attach(
        session, owner, row.id, b"%PDF-1.4\nfixture\n%%EOF"
    )
    reviewer = User(email="reviewer-http@example.com", display_name="Reviewer")
    session.add(reviewer)
    await session.flush()
    session.add(
        ReviewMembership(
            user_id=reviewer.id, scope="operations", environment="production"
        )
    )
    await session.commit()
    actor["id"] = reviewer.id
    response = await api.get(f"/api/v1/review/imports/{row.id}/document")
    assert response.status_code == 200, response.text
    assert response.headers["content-disposition"].startswith("attachment;")
    assert response.headers["content-type"] == "application/octet-stream"
    assert "no-store" in response.headers["cache-control"]
    assert response.headers["x-content-type-options"] == "nosniff"
