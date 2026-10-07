"""Purpose: Serve the signed-in worker's own portable record.

Dependencies: FastAPI, SQLAlchemy async sessions, app.services.worker_record.
Used by: the worker profile, portable record, outcomes and credentials screens.
"""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.auth import current_user
from app.db.session import get_db_session
from app.models.domain import User
from app.schemas.api import ApiModel
from app.services import worker_record as record_service

router = APIRouter(prefix="/me", tags=["worker record"])


class RecordAssessment(ApiModel):
    decision: bool
    confidence: float
    #: Not returned by the scoring service yet.
    score: float | None = None
    band: str
    status: str
    signals_used: list[str]
    explanation_summary: str


class RecordStats(ApiModel):
    completed_jobs: int
    completion_rate: float | None = None
    repeat_hires: int
    disputes: int


class RecordOutcomeItem(ApiModel):
    id: UUID
    title: str
    occurred_at: datetime
    amount: Decimal | None = None
    status: str


class IdentityCredentialItem(ApiModel):
    nin_verified: bool
    bvn_verified: bool
    verified_at: datetime


class GuarantorCredentialItem(ApiModel):
    name: str
    verified: bool
    status: str
    activated_at: datetime
    valid_until: datetime


class ImportedRecordItem(ApiModel):
    verified_outcomes: int
    updated_at: datetime


class RecordCredentials(ApiModel):
    identity: IdentityCredentialItem | None = None
    guarantor: GuarantorCredentialItem | None = None
    imported_record: ImportedRecordItem | None = None


class WorkerRecordResponse(ApiModel):
    worker_id: UUID
    name: str
    role: str | None = None
    avatar_url: str | None = None
    identity_verified: bool
    assessment: RecordAssessment
    verified_outcomes: int
    last_updated: datetime
    stats: RecordStats
    #: Completed jobs, newest first.
    outcomes: list[RecordOutcomeItem]
    credentials: RecordCredentials


@router.get("/record", response_model=WorkerRecordResponse, summary="The worker's portable record")
async def worker_record(
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_db_session),
) -> WorkerRecordResponse:
    try:
        record = await record_service.load_record(session, user)
    except record_service.NotAWorkerError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error

    # Assessing stores (or reuses) the worker's assessment.
    await session.commit()

    return WorkerRecordResponse(
        worker_id=record.worker_id,
        name=record.name,
        role=record.role,
        avatar_url=record.avatar_url,
        identity_verified=record.identity_verified,
        assessment=RecordAssessment(
            decision=record.decision,
            confidence=float(record.confidence),
            score=record.score,
            band=record.band,
            status=record.status,
            signals_used=record.signals_used,
            explanation_summary=record.explanation_summary,
        ),
        verified_outcomes=record.verified_outcomes,
        last_updated=record.last_updated,
        stats=RecordStats(
            completed_jobs=record.completed_jobs,
            completion_rate=record.completion_rate,
            repeat_hires=record.repeat_hires,
            disputes=record.disputes,
        ),
        outcomes=[
            RecordOutcomeItem(
                id=item.id,
                title=item.title,
                occurred_at=item.occurred_at,
                amount=item.amount,
                status=item.status,
            )
            for item in record.outcomes
        ],
        credentials=RecordCredentials(
            identity=IdentityCredentialItem(
                nin_verified=record.identity.nin_verified,
                bvn_verified=record.identity.bvn_verified,
                verified_at=record.identity.verified_at,
            )
            if record.identity
            else None,
            guarantor=GuarantorCredentialItem(
                name=record.guarantor.name,
                verified=record.guarantor.verified,
                status=record.guarantor.status,
                activated_at=record.guarantor.activated_at,
                valid_until=record.guarantor.valid_until,
            )
            if record.guarantor
            else None,
            imported_record=ImportedRecordItem(
                verified_outcomes=record.imported_record.verified_outcomes,
                updated_at=record.imported_record.updated_at,
            )
            if record.imported_record
            else None,
        ),
    )
