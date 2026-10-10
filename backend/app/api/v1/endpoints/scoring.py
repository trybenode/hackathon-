"""Purpose: Let a platform read and set its own scoring settings (SRS FR-1.3, FR-10.3).

Dependencies: FastAPI, SQLAlchemy async sessions, app.services.scoring_config.
Used by: platform integrations; the trust query then scores with them.

Settings belong to the calling key's platform and environment: a sandbox
key's settings never change how production keys score.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.platform_auth import require_tenant
from app.db.session import get_db_session
from app.models.portability import PlatformKey
from app.schemas.api import ApiModel, PlatformType
from app.services import scoring_config as service

router = APIRouter(prefix="/platform/scoring-config", tags=["platform scoring"])


class ScoringSettingsView(ApiModel):
    platform_type: PlatformType
    #: False while the preset for the platform type applies.
    custom: bool
    #: Signal -> weight; they add up to 1.
    weights: dict[str, float]
    #: Without these signals a worker stays in Building History.
    required_signals: list[str]
    #: Signal -> highest raw rate allowed before the worker fails outright.
    hard_fail: dict[str, float]
    #: Jobs needed before a worker is scored at all.
    min_jobs: int
    high_threshold: float
    medium_threshold: float


class ScoringSettingsUpdate(ApiModel):
    weights: dict[str, float]
    required_signals: list[str] = Field(default_factory=list)
    hard_fail: dict[str, float] = Field(default_factory=dict)
    min_jobs: int
    high_threshold: float
    medium_threshold: float


class ScoringSettingsList(ApiModel):
    #: The signals weights, required signals and hard-fail rules can name.
    signals: list[str]
    items: list[ScoringSettingsView]


def _view(settings: service.ScoringSettings) -> ScoringSettingsView:
    return ScoringSettingsView(
        platform_type=settings.platform_type,
        custom=settings.custom,
        weights=settings.weights,
        required_signals=settings.required_signals,
        hard_fail=settings.hard_fail,
        min_jobs=settings.min_jobs,
        high_threshold=settings.high_threshold,
        medium_threshold=settings.medium_threshold,
    )


@router.get("", response_model=ScoringSettingsList, summary="Read your scoring settings")
async def read_settings(
    principal: PlatformKey = Depends(require_tenant),
    session: AsyncSession = Depends(get_db_session),
) -> ScoringSettingsList:
    return ScoringSettingsList(
        signals=service.SIGNALS,
        items=[_view(item) for item in await service.all_settings(session, principal)],
    )


@router.put("/{platform_type}", response_model=ScoringSettingsView, summary="Set your scoring settings")
async def save_settings(
    platform_type: PlatformType,
    payload: ScoringSettingsUpdate,
    principal: PlatformKey = Depends(require_tenant),
    session: AsyncSession = Depends(get_db_session),
) -> ScoringSettingsView:
    """Weights must add up to 1 and thresholds satisfy 0 < medium < high ≤ 1."""

    try:
        saved = await service.save(
            session,
            principal,
            service.ScoringSettings(platform_type=platform_type.value, custom=True, **payload.model_dump()),
        )
    except service.InvalidScoringConfigError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    await session.commit()
    return _view(saved)


@router.delete("/{platform_type}", response_model=ScoringSettingsView, summary="Go back to the preset")
async def reset_settings(
    platform_type: PlatformType,
    principal: PlatformKey = Depends(require_tenant),
    session: AsyncSession = Depends(get_db_session),
) -> ScoringSettingsView:
    restored = await service.reset(session, principal, platform_type.value)
    await session.commit()
    return _view(restored)
