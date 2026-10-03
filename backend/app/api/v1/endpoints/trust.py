"""Purpose: Expose platform trust assessment over persisted worker history.

Dependencies: FastAPI, app.schemas.api, and the shared assessment service.
Used by: platform onboarding clients and outcome-ingestion integrations.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.core.platform_auth import require_platform_api_key
from app.schemas.api import TrustQueryRequest, TrustQueryResponse
from app.services.trust_scoring.assessment import UnknownWorkerError, assess_worker

router = APIRouter(prefix="/trust", tags=["trust"])


@router.post(
    "/query",
    response_model=TrustQueryResponse,
    summary="Assess a worker for onboarding",
)
async def query_trust(
    payload: TrustQueryRequest,
    _: None = Depends(require_platform_api_key),
    session: AsyncSession = Depends(get_db_session),
) -> TrustQueryResponse:
    """Score verified normalized history and persist/reuse its assessment."""

    try:
        result = await assess_worker(
            session,
            payload.worker_id,
            payload.platform_type.value,
            job_context={
                "job_type": payload.job_context.job_type,
                "value_band": payload.job_context.value_band.value,
            },
        )
    except UnknownWorkerError as error:
        raise HTTPException(status_code=404, detail="Worker not found") from error

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
    )
