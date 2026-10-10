"""Purpose: Expose platform trust assessment over persisted worker history.

Dependencies: FastAPI, app.schemas.api, and the shared assessment service.
Used by: platform onboarding clients and outcome-ingestion integrations.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.core.platform_auth import require_platform_api_key
from app.models.portability import PlatformKey
from app.services.platform_history import authorize_assessment
from app.schemas.api import TrustQueryRequest, TrustQueryResponse, WorkerVerification
from app.services import scoring_config
from app.services.worker_verification import verification_for_id
from app.schemas.portability import ApiError
from app.services.trust_scoring.assessment import UnknownWorkerError, assess_worker

router = APIRouter(prefix="/trust", tags=["trust"], responses={code: {"model": ApiError} for code in (401, 403, 404, 422, 503)})


@router.post(
    "/query",
    response_model=TrustQueryResponse,
    summary="Assess a worker for onboarding",
)
async def query_trust(
    payload: TrustQueryRequest,
    principal: PlatformKey | None = Depends(require_platform_api_key),
    session: AsyncSession = Depends(get_db_session),
) -> TrustQueryResponse:
    """Score verified normalized history and persist/reuse its assessment."""

    own = None
    if principal is not None:
        await authorize_assessment(session, principal, payload.worker_id)
        # The platform's saved settings for this platform type, if any.
        own = await scoring_config.for_platform(session, principal, payload.platform_type.value)
    try:
        result = await assess_worker(
            session,
            payload.worker_id,
            payload.platform_type.value,
            job_context={
                "job_type": payload.job_context.job_type,
                "value_band": payload.job_context.value_band.value,
            },
            config=own[0] if own else None,
            policy_name=own[1] if own else None,
        )
    except UnknownWorkerError as error:
        raise HTTPException(status_code=404, detail="Worker not found") from error

    checks = await verification_for_id(session, result.worker_id)
    await session.commit()
    return TrustQueryResponse(
        worker_id=result.worker_id,
        decision=result.decision,
        confidence=result.confidence,
        band=result.band,
        status=result.status,
        signals_used=result.signals_used,
        explanation_summary=result.explanation_summary,
        platform_type_applied=payload.platform_type,
        verification=WorkerVerification(
            identity=checks.identity,
            liveness=checks.liveness,
            guarantor=checks.guarantor,
            guarantor_valid_until=checks.guarantor_valid_until,
        ),
    )
