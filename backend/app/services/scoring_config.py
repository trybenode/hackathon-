"""Purpose: Let a platform set its own scoring weights, thresholds and rules (SRS FR-1.3).

Dependencies: SQLAlchemy async sessions, app.models.developer, and the presets
and signal list in app.services.trust_scoring.scoring.
Used by: the platform scoring-config endpoints and the trust query, which
scores with a platform's settings when it has saved some.

Settings are per platform, environment and platform type. Without saved
settings the preset for the platform type applies, as before.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.developer import ScoringConfig
from app.models.portability import PlatformKey
from app.schemas.api import PlatformType
from app.services.trust_scoring.scoring import NORMALIZERS, PRESETS, PlatformConfig

SIGNALS = sorted(NORMALIZERS)
#: Weights must add up to 1, give or take rounding.
WEIGHT_TOLERANCE = 0.01


class InvalidScoringConfigError(Exception):
    """Settings the scoring formula cannot use."""


@dataclass(frozen=True)
class ScoringSettings:
    platform_type: str
    #: False while the preset applies.
    custom: bool
    weights: dict[str, float]
    required_signals: list[str]
    hard_fail: dict[str, float] = field(default_factory=dict)
    min_jobs: int = 5
    high_threshold: float = 0.80
    medium_threshold: float = 0.60


def preset(platform_type: str) -> PlatformConfig:
    return PRESETS.get(platform_type, PRESETS["generic"])


def _from_config(platform_type: str, config: PlatformConfig, *, custom: bool) -> ScoringSettings:
    return ScoringSettings(
        platform_type=platform_type,
        custom=custom,
        weights=dict(config.weights),
        required_signals=list(config.required_signals),
        hard_fail=dict(config.hard_fail),
        min_jobs=config.min_jobs,
        high_threshold=config.high_t,
        medium_threshold=config.medium_t,
    )


def _to_config(row: ScoringConfig) -> PlatformConfig:
    return PlatformConfig(
        weights=dict(row.weights),
        required_signals=tuple(row.required_signals),
        hard_fail=dict(row.hard_fail or {}),
        min_jobs=row.min_jobs,
        high_t=row.high_threshold,
        medium_t=row.medium_threshold,
    )


def policy_name(organization_id: UUID, environment: str, platform_type: str) -> str:
    """The trust policy a platform's own settings are recorded under."""

    return f"org:{organization_id}:{environment}:{platform_type}"


async def _row(session: AsyncSession, principal: PlatformKey, platform_type: str) -> ScoringConfig | None:
    return await session.scalar(
        select(ScoringConfig).where(
            ScoringConfig.organization_id == principal.organization_id,
            ScoringConfig.environment == principal.environment,
            ScoringConfig.platform_type == platform_type,
        )
    )


async def for_platform(
    session: AsyncSession, principal: PlatformKey, platform_type: str
) -> tuple[PlatformConfig, str] | None:
    """The platform's own settings and policy name, or None to use the preset."""

    row = await _row(session, principal, platform_type)
    if row is None:
        return None
    return _to_config(row), policy_name(principal.organization_id, principal.environment, platform_type)


async def all_settings(session: AsyncSession, principal: PlatformKey) -> list[ScoringSettings]:
    """Every platform type, with the platform's settings where it saved some."""

    result = []
    for platform_type in PlatformType:
        row = await _row(session, principal, platform_type.value)
        config = _to_config(row) if row else preset(platform_type.value)
        result.append(_from_config(platform_type.value, config, custom=row is not None))
    return result


def validate(settings: ScoringSettings) -> None:
    """Refuse settings the formula cannot score with, saying what to fix."""

    if not settings.weights:
        raise InvalidScoringConfigError("Give at least one signal a weight.")
    unknown = sorted((set(settings.weights) | set(settings.hard_fail)) - set(SIGNALS))
    if unknown:
        raise InvalidScoringConfigError(f"Unknown signals: {', '.join(unknown)}. Use: {', '.join(SIGNALS)}.")
    if any(not 0 < weight <= 1 for weight in settings.weights.values()):
        raise InvalidScoringConfigError("Each weight must be above 0 and at most 1.")
    total = sum(settings.weights.values())
    if abs(total - 1) > WEIGHT_TOLERANCE:
        raise InvalidScoringConfigError(f"Weights must add up to 1; these add up to {total:.2f}.")
    missing = [name for name in settings.required_signals if name not in settings.weights]
    if missing:
        raise InvalidScoringConfigError(f"Required signals must also have a weight: {', '.join(missing)}.")
    if any(not 0 <= limit <= 1 for limit in settings.hard_fail.values()):
        raise InvalidScoringConfigError("Hard-fail limits are rates between 0 and 1.")
    if not 1 <= settings.min_jobs <= 200:
        raise InvalidScoringConfigError("The minimum number of jobs must be between 1 and 200.")
    if not 0 < settings.medium_threshold < settings.high_threshold <= 1:
        raise InvalidScoringConfigError("Thresholds must satisfy 0 < medium < high ≤ 1.")


async def save(session: AsyncSession, principal: PlatformKey, settings: ScoringSettings) -> ScoringSettings:
    validate(settings)
    row = await _row(session, principal, settings.platform_type)
    if row is None:
        row = ScoringConfig(
            organization_id=principal.organization_id,
            environment=principal.environment,
            platform_type=settings.platform_type,
        )
        session.add(row)
    row.weights = dict(settings.weights)
    row.required_signals = list(settings.required_signals)
    row.hard_fail = dict(settings.hard_fail)
    row.min_jobs = settings.min_jobs
    row.high_threshold = settings.high_threshold
    row.medium_threshold = settings.medium_threshold
    await session.flush()
    return _from_config(settings.platform_type, _to_config(row), custom=True)


async def reset(session: AsyncSession, principal: PlatformKey, platform_type: str) -> ScoringSettings:
    """Back to the preset for this platform type."""

    row = await _row(session, principal, platform_type)
    if row is not None:
        await session.delete(row)
        await session.flush()
    return _from_config(platform_type, preset(platform_type), custom=False)
