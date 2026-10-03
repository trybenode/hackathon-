"""Purpose: Serve authenticated workers their signed portable credential bundles.

Dependencies: FastAPI auth/session dependencies, credential service, and shared assessment.
Used by: worker profile clients and platform mobility flows.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.auth import current_user
from app.core.config import get_settings
from app.db.session import get_db_session
from app.models.domain import User, Worker
from app.schemas.api import (
    CredentialsExportResponse,
    CredentialsImportRequest,
    CredentialsImportResponse,
)
from app.services import credentials as credential_service
from app.services.trust_scoring.assessment import assess_worker

router = APIRouter(prefix="/workers", tags=["credentials"])
settings = get_settings()

# Ensures workers only touch their own credentials, not someone else's. Raises 404 if the worker is not found or does not belong to the current user.
async def _require_own_worker(
    session: AsyncSession, worker_id: UUID, user: User
) -> Worker:
    worker = await session.scalar(
        select(Worker).where(Worker.id == worker_id, Worker.user_id == user.id)
    )
    if worker is None:
        raise HTTPException(status_code=404, detail="Worker not found")
    return worker

# When a worker requests their own credentials, this endpoint fetches all their verified outcomes, scores them, and returns a signed token that can be imported into another platform.
@router.get(
    "/{worker_id}/credentials/export",
    response_model=CredentialsExportResponse,
    summary="Export verified work history",
)
async def export_worker_credentials(
    worker_id: UUID,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_db_session),
) -> CredentialsExportResponse:
    await _require_own_worker(session, worker_id, user)
    try:
        response = await credential_service.export_credentials(
            session, worker_id, settings.credential_signing_secret
        )
    except credential_service.CredentialTokenError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    await session.commit()
    return response

# When a worker imports a signed credential token from another platform, this endpoint verifies the token, imports the outcomes into the local database, and re-assesses the worker's trust score.
@router.post(
    "/{worker_id}/credentials/import",
    response_model=CredentialsImportResponse,
    summary="Import signed work history",
)
async def import_worker_credentials(
    worker_id: UUID,
    payload: CredentialsImportRequest,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_db_session),
) -> CredentialsImportResponse:
    await _require_own_worker(session, worker_id, user)
    try:
        imported_outcomes = await credential_service.import_credentials(
            session,
            worker_id,
            payload.credential_token,
            payload.source_platform,
            settings.credential_signing_secret,
        )
    except credential_service.CredentialTokenError as error:
        status_code = 503 if "not configured" in str(error) else 422
        raise HTTPException(status_code=status_code, detail=str(error)) from error

    assessment = await assess_worker(session, worker_id, "generic")
    await session.commit()
    return CredentialsImportResponse(
        worker_id=worker_id,
        imported_outcomes=imported_outcomes,
        new_band=assessment.band,
    )
