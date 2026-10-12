"""Purpose: Serve the signed-in worker's own portable record.

Dependencies: FastAPI, SQLAlchemy async sessions, app.services.worker_record.
Used by: the worker profile, portable record, outcomes and credentials screens.
"""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.schemas.portability import HistoryPage, ApiError, VerificationSummary
from app.services.portability import own_history, summary_from_record

from app.api.v1.endpoints.auth import current_user
from app.db.session import get_db_session
from app.models.domain import User
from app.schemas.api import ApiModel
from app.services import worker_record as record_service

router = APIRouter(prefix="/me", tags=["worker record"], responses={code: {"model": ApiError} for code in (401, 404, 422, 503)})


# extract into defined schema file 
class RecordAssessment(ApiModel):
    assessed_at: datetime
    decision: bool
    confidence: float
    #: How good the record is, 0 to 1; null while building history.
    score: float | None = None
    band: str
    status: str
    signals_used: list[str]
    explanation_summary: str


class RecordStats(ApiModel):
    completed_jobs: int
    completion_rate: float | None = None
    repeat_hires: int | None
    disputes: int | None


class RecordOutcomeItem(ApiModel):
    id: UUID
    title: str
    occurred_at: datetime
    amount: Decimal | None = None
    status: str
    location: str | None = None
    client_name: str | None = None
    rating: float | None = None
    #: "none", "dismissed" or "upheld".
    dispute: str = "none"
    source: str = "native"


class RecordOutcomePage(ApiModel):
    items: list[RecordOutcomeItem]
    total: int
    page: int
    size: int
    pages: int


def _outcome_item(item: record_service.RecordOutcome) -> RecordOutcomeItem:
    return RecordOutcomeItem(
        id=item.id,
        title=item.title,
        occurred_at=item.occurred_at,
        amount=item.amount,
        status=item.status,
        location=item.location,
        client_name=item.client_name,
        rating=item.rating,
        dispute=item.dispute,
        source=item.source,
    )


class IdentityCredentialItem(ApiModel):
    status: str
    nin_verified: bool
    bvn_verified: bool
    verified_at: datetime


class GuarantorCredentialItem(ApiModel):
    sandbox: bool
    name: str
    verified: bool
    status: str
    activated_at: datetime
    valid_until: datetime
    relationship: str = ""


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
    identity_status: str
    self_declared_outcomes: int
    total_outcomes: int
    starting_rating: float | None
    starting_rating_label: str | None
    public_summary: VerificationSummary
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
        identity_status=record.identity_status, self_declared_outcomes=record.self_declared_outcomes, total_outcomes=record.total_outcomes, starting_rating=record.starting_rating, starting_rating_label=record.starting_rating_label,
        public_summary=summary_from_record(record),
        assessment=RecordAssessment(
            assessed_at=record.assessed_at,
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
        outcomes=[_outcome_item(item) for item in record.outcomes],
        credentials=RecordCredentials(
            identity=IdentityCredentialItem(
                status=record.identity.status,
                nin_verified=record.identity.nin_verified,
                bvn_verified=record.identity.bvn_verified,
                verified_at=record.identity.verified_at,
            )
            if record.identity
            else None,
            guarantor=GuarantorCredentialItem(
                sandbox=record.guarantor.sandbox,
                name=record.guarantor.name,
                verified=record.guarantor.verified,
                status=record.guarantor.status,
                activated_at=record.guarantor.activated_at,
                valid_until=record.guarantor.valid_until,
                relationship=record.guarantor.relationship,
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


@router.get("/record/outcomes", response_model=RecordOutcomePage, summary="Every completed verified outcome")
async def record_outcomes(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_db_session),
) -> RecordOutcomePage:
    """The record lists only the latest few; this pages through them all."""
    try:
        items, total = await record_service.completed_outcomes(session, user, page=page, size=size)
    except record_service.NotAWorkerError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return RecordOutcomePage(
        items=[_outcome_item(item) for item in items], total=total, page=page, size=size, pages=max(1, -(-total // size))
    )


@router.get("/record/history", response_model=HistoryPage, summary="Read your verified and self-declared history")
async def worker_history(page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=100), user: User = Depends(current_user), session: AsyncSession = Depends(get_db_session)) -> HistoryPage:
    return await own_history(session, user, page, size)
