"""Purpose: Verify sandbox keys reach only the demo workers, and production keys only real ones.

Dependencies: pytest, httpx, and the portability acceptance fixtures.
Used by: the backend test suite and CI.
"""

from uuid import uuid4

from sqlalchemy import func, select

from app.models.domain import NormalizedOutcome, Organization, OrganizationType
from app.models.portability import PlatformKey
from app.services import sandbox
from app.services.portability import digest, now
from tests.api.test_portability_features import api  # noqa: F401  (fixture)

ADA = sandbox.DEMO_WORKERS[0]
QUERY = {"platform_type": "generic", "job_context": {"job_type": "cleaning", "value_band": "low"}}


async def keyed(session, environment: str):
    org = Organization(name=f"Dev {environment}", organization_type=OrganizationType.PLATFORM)
    session.add(org)
    await session.flush()
    secret = f"sk_{environment}_{uuid4().hex}"
    session.add(PlatformKey(organization_id=org.id, key_hash=digest(secret), environment=environment))
    await session.commit()
    return org, {"X-API-Key": secret}


async def test_a_sandbox_key_works_end_to_end_with_a_demo_worker(api, session):
    client, _ = api
    _, headers = await keyed(session, "sandbox")

    linked = await client.post(
        "/api/v1/platform/worker-links", headers=headers,
        json={"external_worker_id": "my-user-1", "consent_token": ADA.consent_token},
    )
    assert linked.status_code == 201, linked.text
    worker_id = linked.json()["worker_id"]

    scored = await client.post("/api/v1/trust/query", headers=headers, json={"worker_id": worker_id, **QUERY})
    assert scored.status_code == 200, scored.text
    assert scored.json()["band"] == "High"

    history = await client.get("/api/v1/platform/workers/my-user-1/history", headers=headers)
    assert history.status_code == 200
    assert history.json()["total"] == ADA.jobs


async def test_sandbox_imports_answer_but_leave_the_demo_worker_alone(api, session):
    client, _ = api
    _, headers = await keyed(session, "sandbox")
    await client.post(
        "/api/v1/platform/worker-links", headers=headers,
        json={"external_worker_id": "my-user-1", "consent_token": ADA.consent_token},
    )
    before = await session.scalar(select(func.count()).select_from(NormalizedOutcome))

    payload = {"outcomes": [{"source_record_id": "job-1", "occurred_at": now().isoformat(), "status": "completed", "dispute_resolution": None}]}
    imported = await client.post(
        "/api/v1/platform/workers/my-user-1/history/import",
        headers={**headers, "Idempotency-Key": "batch-1"}, json=payload,
    )

    assert imported.status_code == 200, imported.text
    assert imported.json()["imported_outcomes"] == 1
    assert await session.scalar(select(func.count()).select_from(NormalizedOutcome)) == before


async def test_a_sandbox_key_cannot_reach_a_real_worker(api, session):
    client, _ = api
    org, headers = await keyed(session, "sandbox")

    grant = await client.post(
        "/api/v1/me/worker/platform-grants",
        json={"organization_id": str(org.id), "permissions": ["read_history"]},
    )
    refused = await client.post(
        "/api/v1/platform/worker-links", headers=headers,
        json={"external_worker_id": "real-1", "consent_token": grant.json()["token"]},
    )

    assert refused.status_code == 403
    assert refused.json()["code"] == "ENVIRONMENT_MISMATCH"


async def test_a_production_key_cannot_use_demo_workers(api, session):
    client, _ = api
    _, sandbox_headers = await keyed(session, "sandbox")
    _, live_headers = await keyed(session, "production")

    by_token = await client.post(
        "/api/v1/platform/worker-links", headers=live_headers,
        json={"external_worker_id": "x", "consent_token": ADA.consent_token},
    )
    assert by_token.status_code == 403

    linked = await client.post(
        "/api/v1/platform/worker-links", headers=sandbox_headers,
        json={"external_worker_id": "my-user-1", "consent_token": ADA.consent_token},
    )
    by_id = await client.post(
        "/api/v1/trust/query", headers=live_headers, json={"worker_id": linked.json()["worker_id"], **QUERY}
    )
    assert by_id.status_code == 403
    assert by_id.json()["code"] == "ENVIRONMENT_MISMATCH"


async def test_calls_with_a_platform_key_are_logged_without_identifiers(api, session):
    from app.models.developer import ApiRequestLog

    client, _ = api
    _, headers = await keyed(session, "sandbox")
    await client.post(
        "/api/v1/platform/worker-links", headers=headers,
        json={"external_worker_id": "my-user-1", "consent_token": ADA.consent_token},
    )
    await client.get("/api/v1/platform/workers/nobody/history", headers=headers)

    rows = (await session.scalars(select(ApiRequestLog).order_by(ApiRequestLog.created_at))).all()
    assert [(row.method, row.status_code) for row in rows] == [("POST", 201), ("GET", 404)]
    # The route template, never the worker's id.
    assert rows[1].path == "/api/v1/platform/workers/{external_id}/history"


async def test_the_trust_query_reports_what_was_verified(api, session):
    client, _ = api
    _, headers = await keyed(session, "sandbox")
    expected = {
        "ada": ("verified", "verified", "active"),
        "tunde": ("verified", "verified", "pending"),
        "bisi": ("verified", "verified", "none"),
        "chidi": ("verified", "verified", "none"),
    }

    for demo in sandbox.DEMO_WORKERS:
        linked = await client.post(
            "/api/v1/platform/worker-links", headers=headers,
            json={"external_worker_id": f"user-{demo.slug}", "consent_token": demo.consent_token},
        )
        scored = await client.post(
            "/api/v1/trust/query", headers=headers, json={"worker_id": linked.json()["worker_id"], **QUERY}
        )
        checks = scored.json()["verification"]
        assert (checks["identity"], checks["liveness"], checks["guarantor"]) == expected[demo.slug], demo.slug
        assert (checks["guarantor_valid_until"] is not None) == (demo.slug == "ada")


async def test_a_platform_scores_with_its_own_settings(api, session):
    client, _ = api
    _, headers = await keyed(session, "sandbox")
    linked = await client.post(
        "/api/v1/platform/worker-links", headers=headers,
        json={"external_worker_id": "user-1", "consent_token": ADA.consent_token},
    )
    query = {"worker_id": linked.json()["worker_id"], **QUERY}

    listed = await client.get("/api/v1/platform/scoring-config", headers=headers)
    assert listed.status_code == 200
    assert "completion_rate" in listed.json()["signals"]
    assert all(not item["custom"] for item in listed.json()["items"])

    strict = {"weights": {"completion_rate": 0.5, "dispute_rate": 0.5}, "required_signals": ["completion_rate"],
              "min_jobs": 100, "high_threshold": 0.9, "medium_threshold": 0.7}
    saved = await client.put("/api/v1/platform/scoring-config/generic", headers=headers, json=strict)
    assert saved.status_code == 200, saved.text and saved.json()["custom"]
    scored = await client.post("/api/v1/trust/query", headers=headers, json=query)
    assert scored.json()["band"] == "Building History"

    bad = await client.put("/api/v1/platform/scoring-config/generic", headers=headers,
                           json={**strict, "weights": {"completion_rate": 0.2}})
    assert bad.status_code == 422

    await client.delete("/api/v1/platform/scoring-config/generic", headers=headers)
    rescored = await client.post("/api/v1/trust/query", headers=headers, json=query)
    assert rescored.json()["band"] == "High"
