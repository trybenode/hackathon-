"""Purpose: Verify the sandbox demo workers and their published consent tokens.

Dependencies: pytest, SQLAlchemy async sessions, app.services.sandbox.
Used by: the backend test suite and CI.
"""

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.domain import Organization, OrganizationType, Worker
from app.models.portability import PlatformKey
from app.services import sandbox
from app.services.trust_scoring.assessment import assess_worker


async def key(session: AsyncSession, environment: str) -> PlatformKey:
    org = Organization(name="Acme Hire", organization_type=OrganizationType.PLATFORM)
    session.add(org)
    await session.flush()
    principal = PlatformKey(organization_id=org.id, key_hash=f"hash-{environment}-{org.id}", environment=environment)
    session.add(principal)
    await session.flush()
    return principal


async def test_demo_workers_are_seeded_once(session: AsyncSession) -> None:
    first = await sandbox.ensure_demo_workers(session)
    second = await sandbox.ensure_demo_workers(session)

    assert set(first) == {"ada", "tunde", "bisi", "chidi"}
    assert {w.id for w in first.values()} == {w.id for w in second.values()}
    assert all(worker.is_sandbox for worker in first.values())
    count = await session.scalar(select(func.count()).select_from(Worker).where(Worker.is_sandbox.is_(True)))
    assert count == 4


@pytest.mark.parametrize("slug", ["ada", "tunde", "bisi", "chidi"])
async def test_each_demo_worker_lands_in_its_band(session: AsyncSession, slug: str) -> None:
    workers = await sandbox.ensure_demo_workers(session)
    demo = next(d for d in sandbox.DEMO_WORKERS if d.slug == slug)

    result = await assess_worker(session, workers[slug].id, "generic")

    assert result.band == demo.band


async def test_demo_tokens_work_only_for_sandbox_keys(session: AsyncSession) -> None:
    token = sandbox.DEMO_WORKERS[0].consent_token
    assert len(token) >= 32

    sandbox_key = await key(session, "sandbox")
    production_key = await key(session, "production")

    grant = await sandbox.demo_grant(session, sandbox_key, token)
    assert grant is not None and grant.organization_id == sandbox_key.organization_id
    # Asking again returns the same approval.
    assert (await sandbox.demo_grant(session, sandbox_key, token)).id == grant.id
    assert await sandbox.demo_grant(session, production_key, token) is None
    assert await sandbox.demo_grant(session, sandbox_key, "not-a-demo-token") is None
