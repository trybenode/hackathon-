"""Worker ownership, public summaries, platform consent and customer reviews."""
from uuid import UUID
from math import ceil
from fastapi import APIRouter, Depends, Header, Query, Request, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.v1.endpoints.auth import current_user
from app.core.platform_auth import require_tenant
from app.db.session import get_db_session
from app.models.domain import Organization, User
from app.models.portability import PlatformGrant, PlatformKey, ShareGrant
from app.schemas.portability import ApiError, GrantList, GrantResponse, HistoryImportRequest, HistoryImportResponse, HistoryPage, PlatformCatalog, PlatformGrantRequest, PlatformOption, ReviewEligibility, ReviewRequest, ReviewResponse, VerificationSummary, WorkerLinkRequest, WorkerLinkResponse, WorkerRecord
from app.services import platform_history, portability, reviews

ERRORS = {code: {"model": ApiError} for code in [401, 403, 404, 409, 410, 422, 429, 503]}
router = APIRouter(tags=["portable records"], responses=ERRORS)
platform_router = APIRouter(prefix="/platform", tags=["platform history"], responses=ERRORS)


@router.get("/me/worker/record", response_model=WorkerRecord, summary="Read your current portable record")
async def record(page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=100), user: User = Depends(current_user), session: AsyncSession = Depends(get_db_session)):
    worker = await portability.own_worker(session, user)
    result = await portability.worker_record(session, worker, page=page, size=size)
    await session.commit()
    return result


@router.post("/me/worker/shares", response_model=GrantResponse, status_code=201, summary="Share a standard verification summary")
async def issue_share(user: User = Depends(current_user), session: AsyncSession = Depends(get_db_session)):
    result = await portability.issue_grant(session, user)
    await session.commit()
    return result


@router.get("/me/worker/shares", response_model=GrantList, summary="List your public share links")
async def shares(page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=100), user: User = Depends(current_user), session: AsyncSession = Depends(get_db_session)):
    return await portability.list_grants(session, user, ShareGrant, page, size)


@router.delete("/me/worker/shares/{grant_id}", status_code=204, summary="Revoke your public share link")
async def revoke_share(grant_id: UUID, user: User = Depends(current_user), session: AsyncSession = Depends(get_db_session)):
    await portability.revoke_grant(session, user, ShareGrant, grant_id)
    await session.commit()


@router.get("/verification/{token}", response_model=VerificationSummary, summary="Read a live verification summary", description="No login required. Standard summary only; expired or revoked links return 410. Does not grant access to documents or detailed history.")
async def verification(token: str, session: AsyncSession = Depends(get_db_session)):
    result = await portability.public_summary(session, token)
    await session.commit()
    return result


@router.get("/me/worker/platforms", response_model=PlatformCatalog, summary="List available named platforms")
async def platforms(page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=100), user: User = Depends(current_user), session: AsyncSession = Depends(get_db_session)):
    await portability.own_worker(session, user)
    eligible = Organization.id.in_(select(PlatformKey.organization_id).where(PlatformKey.revoked_at.is_(None)))
    total = await session.scalar(select(func.count()).select_from(Organization).where(eligible))
    rows = (await session.scalars(select(Organization).where(eligible).order_by(Organization.name, Organization.id).offset((page-1)*size).limit(size))).all()
    return PlatformCatalog(items=[PlatformOption(id=r.id, name=r.name) for r in rows], total=total, page=page, size=size, pages=ceil(total/size))


@router.post("/me/worker/platform-grants", response_model=GrantResponse, status_code=201, summary="Approve a named platform", description="Worker approves read_history, import_history, or both for seven days. The random consent token is returned once; it must be sent privately to the named platform.")
async def issue_platform_grant(payload: PlatformGrantRequest, user: User = Depends(current_user), session: AsyncSession = Depends(get_db_session)):
    result = await portability.issue_grant(session, user, organization_id=payload.organization_id, permissions=payload.permissions)
    await session.commit()
    return result


@router.get("/me/worker/platform-grants", response_model=GrantList, summary="List your platform approvals")
async def platform_grants(page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=100), user: User = Depends(current_user), session: AsyncSession = Depends(get_db_session)):
    return await portability.list_grants(session, user, PlatformGrant, page, size)


@router.delete("/me/worker/platform-grants/{grant_id}", status_code=204, summary="Revoke a platform approval")
async def revoke_platform_grant(grant_id: UUID, user: User = Depends(current_user), session: AsyncSession = Depends(get_db_session)):
    await portability.revoke_grant(session, user, PlatformGrant, grant_id)
    await session.commit()


@platform_router.post("/worker-links", response_model=WorkerLinkResponse, status_code=201, summary="Bind your worker ID using worker consent")
async def worker_link(payload: WorkerLinkRequest, principal: PlatformKey = Depends(require_tenant), session: AsyncSession = Depends(get_db_session)):
    result = await platform_history.link_worker(session, principal, payload.external_worker_id, payload.consent_token)
    await session.commit()
    return result


@platform_router.get("/workers/{external_id}/history", response_model=HistoryPage, summary="Read approved history and provenance")
async def history(external_id: str, page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=100), principal: PlatformKey = Depends(require_tenant), session: AsyncSession = Depends(get_db_session)):
    return await platform_history.read_history(session, principal, external_id, page, size)


@platform_router.post("/workers/{external_id}/history/import", response_model=HistoryImportResponse, summary="Import historical evidence", description="100 records maximum per batch. Idempotency-Key is required. attest requires a reviewed platform credential; API submission alone does not establish verification.")
async def ingest(external_id: str, payload: HistoryImportRequest, idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=128), principal: PlatformKey = Depends(require_tenant), session: AsyncSession = Depends(get_db_session)):
    result = await platform_history.import_history(session, principal, external_id, payload, idempotency_key)
    await session.commit()
    return result


@router.get("/jobs/{job_id}/review-eligibility", response_model=ReviewEligibility, summary="Check your review eligibility and receipt")
async def review_eligibility(job_id: UUID, user: User = Depends(current_user), session: AsyncSession = Depends(get_db_session)):
    result, _, _ = await reviews.eligibility(session, user, job_id)
    return result


@router.post("/jobs/{job_id}/review", response_model=ReviewResponse, status_code=201, summary="Review a completed protected independent job", description="One review per job. Requires verified customer identity, explicit dual confirmation, completed outcome, funded escrow, confirmed premium and cover evidence. Redis limits attempts; database limits successful reviews over 24h. Matching idempotent replays return the receipt.")
async def review(job_id: UUID, payload: ReviewRequest, request: Request, idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=128), user: User = Depends(current_user), session: AsyncSession = Depends(get_db_session)):
    await reviews.limit_attempts(str(user.id), request.client.host if request.client else "unknown")
    result = await reviews.submit_review(session, user, job_id, payload, idempotency_key)
    await session.commit()
    return result
