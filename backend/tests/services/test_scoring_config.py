"""Purpose: Verify a platform's own scoring settings are checked, kept apart, and used.

Dependencies: pytest, SQLAlchemy async sessions, app.services.scoring_config.
Used by: the backend test suite and CI.
"""

from dataclasses import replace

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.domain import Organization, OrganizationType
from app.models.portability import PlatformKey
from app.services import sandbox
from app.services import scoring_config as service
from app.services.trust_scoring.assessment import assess_worker

STRICT = service.ScoringSettings(
    platform_type="generic",
    custom=True,
    weights={"completion_rate": 0.5, "dispute_rate": 0.5},
    required_signals=["completion_rate"],
    min_jobs=100,
    high_threshold=0.9,
    medium_threshold=0.7,
)


async def key(session: AsyncSession, environment: str = "production", org: Organization | None = None) -> PlatformKey:
    if org is None:
        org = Organization(name="Acme Hire", organization_type=OrganizationType.PLATFORM)
        session.add(org)
        await session.flush()
    principal = PlatformKey(organization_id=org.id, key_hash=f"h-{environment}-{org.id}", environment=environment)
    session.add(principal)
    await session.flush()
    return principal


async def test_presets_apply_until_settings_are_saved(session: AsyncSession) -> None:
    principal = await key(session)

    settings = {item.platform_type: item for item in await service.all_settings(session, principal)}

    assert set(settings) == {"domestic", "handyman", "ride_hailing", "generic"}
    assert not any(item.custom for item in settings.values())
    assert settings["domestic"].min_jobs == 8
    assert await service.for_platform(session, principal, "generic") is None


@pytest.mark.parametrize(
    "change, message",
    [
        ({"weights": {}}, "at least one"),
        ({"weights": {"completion_rate": 0.5, "speed": 0.5}}, "Unknown signals: speed"),
        ({"weights": {"completion_rate": 0.5, "dispute_rate": 0.4}}, "add up to 1"),
        ({"required_signals": ["no_show_rate"]}, "must also have a weight"),
        ({"hard_fail": {"dispute_rate": 2}}, "between 0 and 1"),
        ({"min_jobs": 0}, "between 1 and 200"),
        ({"high_threshold": 0.5, "medium_threshold": 0.6}, "medium < high"),
    ],
)
async def test_unusable_settings_are_refused(session: AsyncSession, change: dict, message: str) -> None:
    with pytest.raises(service.InvalidScoringConfigError, match=message):
        await service.save(session, await key(session), replace(STRICT, **change))


async def test_saved_settings_change_the_score_and_reset_restores_it(session: AsyncSession) -> None:
    principal = await key(session)
    ada = (await sandbox.ensure_demo_workers(session))["ada"]

    await service.save(session, principal, STRICT)
    config, policy = await service.for_platform(session, principal, "generic")
    strict = await assess_worker(session, ada.id, "generic", config=config, policy_name=policy)
    default = await assess_worker(session, ada.id, "generic")

    assert default.band == "High"
    # Ada has 48 jobs; this platform wants 100 before it scores anyone.
    assert strict.band == "Building History"

    restored = await service.reset(session, principal, "generic")
    assert restored.custom is False
    assert await service.for_platform(session, principal, "generic") is None


async def test_sandbox_settings_leave_production_alone(session: AsyncSession) -> None:
    production = await key(session)
    org = await session.get(Organization, production.organization_id)
    sandbox_key = await key(session, "sandbox", org)

    await service.save(session, sandbox_key, STRICT)

    assert await service.for_platform(session, sandbox_key, "generic") is not None
    assert await service.for_platform(session, production, "generic") is None
