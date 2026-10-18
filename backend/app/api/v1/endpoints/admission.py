"""Session-scoped ownership imports/reviewer queues and tenant policy APIs; delegates domain rules."""

from datetime import timedelta
from uuid import UUID
from typing import Literal
from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Header,
    Query,
    Request,
    Response,
    UploadFile,
)
from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.v1.endpoints.auth import current_user
from app.core.config import get_settings
from app.core.platform_auth import require_tenant_scope
from app.db.session import get_db_session
from app.models.admission import OnboardingCase, OwnershipImport, ReviewMembership
from app.models.domain import User, Worker
from app.models.portability import PlatformKey
from app.schemas.admission import (
    CaseCreate,
    DecisionInput,
    ImportPage,
    ImportView,
    OnboardingView,
    PolicyUpdate,
    ProvisionalView,
    VersionInput,
)
from app.schemas.admission import (
    ReviewAccess,
    VerificationCapabilities,
    PolicyView,
    ImportDetail,
    CasePage,
)
from app.schemas.portability import ApiError
from app.services import admission, ownership_imports, review_storage
from app.services.feature_common import FeatureError, now, digest, aware, audit
from app.services.review_access import reviewer, worker_for


async def guard(request: Request, user: User = Depends(current_user)) -> None:
    """Bound mutations across replicas and reject cross-origin session writes."""
    if request.method in {"GET", "HEAD", "OPTIONS"}:
        return
    cfg = get_settings()
    if (
        cfg.environment != "development"
        and request.headers.get("origin") not in cfg.cors_origin_list
    ):
        raise FeatureError(
            403, "ORIGIN_REJECTED", "This request origin is not permitted."
        )
    await mutation_limit(request, str(user.id))


async def mutation_limit(request: Request, identity: str) -> None:
    """Share Redis limits between authenticated reviewer and tenant-key mutations."""
    cfg = get_settings()
    bucket = int(now().timestamp()) // 60
    keys = [
        f"admission:user:{identity}:{bucket}",
        f"admission:ip:{digest(request.client.host if request.client else '')}:{bucket}",
    ]
    script = "local r={} for i,k in ipairs(KEYS) do local n=redis.call('INCR',k) if n==1 then redis.call('EXPIRE',k,60) end r[i]=n end return r"
    try:
        async with Redis.from_url(
            cfg.redis_url, socket_connect_timeout=2, socket_timeout=2
        ) as redis:
            counts = await redis.eval(script, 2, *keys)
    except (RedisError, OSError):
        raise FeatureError(
            503,
            "LIMITER_UNAVAILABLE",
            "Submission is temporarily unavailable. Preserve inputs and retry safely.",
            60,
        ) from None
    if counts[0] > 30 or counts[1] > 120:
        raise FeatureError(
            429, "SUBMISSION_LIMIT", "Wait before submitting another request.", 60
        )


router = APIRouter(
    tags=["additional verification"],
    dependencies=[Depends(guard)],
    responses={
        code: {"model": ApiError} for code in (401, 403, 404, 409, 410, 422, 429, 503)
    },
)
platform_router = APIRouter(
    prefix="/platform/onboarding-policy", tags=["onboarding policy"]
)


@router.get("/me/verification-capabilities", response_model=VerificationCapabilities)
async def capabilities(user: User = Depends(current_user)) -> dict:
    cfg = get_settings()
    return {
        "unsigned_imports_enabled": cfg.unsigned_imports_enabled,
        "additional_verification_enabled": cfg.additional_verification_enabled,
        "csv_max_bytes": ownership_imports.CSV_LIMIT,
        "document_max_bytes": review_storage.MAX_DOCUMENT,
        "max_rows": ownership_imports.ROW_LIMIT,
    }


@router.get("/me/history-imports/template")
async def template(
    user: User = Depends(current_user), session: AsyncSession = Depends(get_db_session)
) -> Response:
    ownership_imports.enabled()
    worker = await worker_for(session, user)
    return Response(
        f"worker_id,job_id,date,status,cancelled_by,source_reference\n{worker.id},example-job,2025-01-01,completed,,example-reference\n",
        media_type="text/csv",
        headers={
            "Content-Disposition": 'attachment; filename="work-history-template.csv"'
        },
    )


@router.post("/me/history-imports", response_model=ImportView, status_code=201)
async def prepare(
    csv_file: UploadFile = File(),
    source_name: str = Form(min_length=1, max_length=120),
    replaces_id: UUID | None = Form(None),
    operation: UUID = Header(alias="Idempotency-Key"),
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ImportView:
    data = await csv_file.read(ownership_imports.CSV_LIMIT + 1)
    await csv_file.close()
    result = await ownership_imports.prepare(
        session, user, data, source_name, operation, replaces_id
    )
    await session.commit()
    return result


@router.get("/me/history-imports", response_model=ImportPage)
async def imports(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ImportPage:
    result = await ownership_imports.page(session, user, page, size)
    await session.commit()
    return result


@router.get("/me/history-imports/operations/{operation}", response_model=ImportView)
async def receipt(
    operation: UUID,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ImportView:
    ownership_imports.enabled()
    worker = await worker_for(session, user)
    row = await session.scalar(
        select(OwnershipImport).where(
            OwnershipImport.worker_id == worker.id,
            OwnershipImport.operation_id == operation,
        )
    )
    if not row:
        raise FeatureError(
            404, "RECEIPT_NOT_FOUND", "No committed import exists for this operation."
        )
    return ownership_imports.view(row)


@router.get("/me/history-imports/{batch_id}", response_model=ImportView)
async def import_status(
    batch_id: UUID,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ImportView:
    ownership_imports.enabled()
    return ownership_imports.view(
        await ownership_imports.owned(session, user, batch_id)
    )


@router.put("/me/history-imports/{batch_id}/document", response_model=ImportView)
async def attach(
    batch_id: UUID,
    document: UploadFile = File(),
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ImportView:
    data = await document.read(review_storage.MAX_DOCUMENT + 1)
    await document.close()
    result = await ownership_imports.attach(session, user, batch_id, data)
    await session.commit()
    return result


@router.post("/me/history-imports/{batch_id}/submit", response_model=ImportView)
async def submit(
    batch_id: UUID,
    payload: VersionInput,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ImportView:
    result = await ownership_imports.submit(session, user, batch_id, payload.version)
    await session.commit()
    return result


@router.post("/me/history-imports/{batch_id}/withdraw", response_model=ImportView)
async def withdraw(
    batch_id: UUID,
    payload: VersionInput,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ImportView:
    result = await ownership_imports.withdraw(session, user, batch_id, payload.version)
    await session.commit()
    return result


@router.get("/me/additional-verification", response_model=OnboardingView | None)
async def onboarding(
    organization_id: UUID | None = None,
    platform_type: Literal["generic", "domestic", "ride_hailing"] = "generic",
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_db_session),
) -> OnboardingView | None:
    worker = await worker_for(session, user)
    result = await admission.evaluate(
        session,
        worker.id,
        str(organization_id) if organization_id else "first_party",
        "production",
        platform_type,
    )
    await session.commit()
    return result


@router.post("/me/additional-verification/cases", response_model=OnboardingView)
async def create_case(
    payload: CaseCreate,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_db_session),
) -> OnboardingView:
    result = await admission.submit_case(session, user, payload)
    await session.commit()
    return result


@router.get("/review/access", response_model=ReviewAccess)
async def access(
    user: User = Depends(current_user), session: AsyncSession = Depends(get_db_session)
) -> dict:
    roles = (
        await session.scalars(
            select(ReviewMembership).where(
                ReviewMembership.user_id == user.id,
                ReviewMembership.revoked_at.is_(None),
            )
        )
    ).all()
    return {"roles": [{"scope": r.scope, "environment": r.environment} for r in roles]}


@router.get("/review/imports", response_model=ImportPage)
async def ownership_queue(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ImportPage:
    await reviewer(session, user, "operations", "production")
    result = await ownership_imports.page(session, user, page, size, operations=True)
    await session.commit()
    return result


@router.get("/review/imports/{batch_id}", response_model=ImportDetail)
async def ownership_detail(
    batch_id: UUID,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    ownership_imports.enabled()
    await reviewer(session, user, "operations", "production")
    row = await session.get(OwnershipImport, batch_id)
    if not row:
        raise FeatureError(404, "IMPORT_NOT_FOUND", "History import not found.")
    worker = await session.get(Worker, row.worker_id)
    person = await session.get(User, worker.user_id)
    from app.services.worker_verification import verification_for

    checks = await verification_for(session, worker)
    from app.services.worker_record import latest_check

    identity = await latest_check(session, worker.user_id)
    return {
        "batch": ownership_imports.view(row).model_dump(mode="json"),
        "worker": {
            "id": worker.id,
            "name": person.display_name,
            "email": person.email,
            "profile_phone": person.phone,
            "identity_reference": (
                {
                    "id": identity.id,
                    "provider": identity.provider,
                    "reference": identity.provider_reference,
                    "checked_at": identity.created_at,
                }
                if identity
                else None
            ),
            "identity": checks.identity,
            "liveness": checks.liveness,
        },
    }


@router.get("/review/imports/{batch_id}/document")
async def document(
    batch_id: UUID,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    ownership_imports.enabled()
    await reviewer(session, user, "operations", "production")
    row = await session.get(OwnershipImport, batch_id)
    if not row or not row.document_key or aware(row.expires_at) <= now():
        raise FeatureError(
            410,
            "DOCUMENT_EXPIRED",
            "Supporting document has expired or is unavailable.",
        )
    data = await review_storage.read(row.document_key)
    suffix = {"application/pdf": "pdf", "image/jpeg": "jpg", "image/png": "png"}[
        row.document_type
    ]
    audit(session, user.id, "ownership_import", row.id, "document_downloaded")
    await session.commit()
    return Response(
        data,
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="supporting-evidence.{suffix}"',
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "sandbox; default-src 'none'",
            "Cache-Control": "no-store, private",
        },
    )


@router.post("/review/imports/{batch_id}/decision", response_model=ImportView)
async def ownership_decision(
    batch_id: UUID,
    payload: DecisionInput,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ImportView:
    result = await ownership_imports.decide(session, user, batch_id, payload)
    await session.commit()
    return result


@router.get("/review/onboarding/{scope}", response_model=CasePage)
async def review_queue(
    scope: str,
    environment: str = Query("production", pattern="^(production|sandbox)$"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    result = await admission.queue(session, user, scope, environment, page, size)
    await session.commit()
    return result


@router.post(
    "/review/onboarding-cases/{case_id}/decision", response_model=OnboardingView
)
async def onboarding_decision(
    case_id: UUID,
    payload: DecisionInput,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_db_session),
) -> OnboardingView:
    result = await admission.decide(session, user, case_id, payload)
    await session.commit()
    return result


@router.get("/review/policies/{scope}/{platform_type}", response_model=PolicyView)
async def get_policy(
    scope: str,
    platform_type: Literal["generic", "domestic", "ride_hailing"],
    environment: str = Query("production", pattern="^(production|sandbox)$"),
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    await reviewer(
        session, user, "operations" if scope == "first_party" else scope, environment
    )
    settings, version = await admission.policy(
        session, scope, environment, platform_type
    )
    return {"version": version, "settings": settings.model_dump(mode="json")}


@router.put("/review/policies/{scope}/{platform_type}", response_model=PolicyView)
async def update_policy(
    scope: str,
    payload: PolicyUpdate,
    platform_type: str,
    environment: str = Query("production", pattern="^(production|sandbox)$"),
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    if platform_type not in {"generic", "domestic", "ride_hailing"}:
        raise FeatureError(422, "POLICY_TYPE", "Unsupported platform type.")
    result = await admission.save_policy(
        session, user, scope, environment, platform_type, payload
    )
    await session.commit()
    return result


@platform_router.get("/{platform_type}", response_model=PolicyView)
async def platform_policy(
    platform_type: Literal["generic", "domestic", "ride_hailing"],
    principal: PlatformKey = Depends(require_tenant_scope("scoring")),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    settings, version = await admission.policy(
        session, str(principal.organization_id), principal.environment, platform_type
    )
    return {"version": version, "settings": settings.model_dump(mode="json")}


@platform_router.put("/{platform_type}", response_model=PolicyView)
async def platform_policy_update(
    request: Request,
    platform_type: str,
    payload: PolicyUpdate,
    principal: PlatformKey = Depends(require_tenant_scope("scoring")),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    if platform_type not in {"generic", "domestic", "ride_hailing"}:
        raise FeatureError(422, "POLICY_TYPE", "Unsupported platform type.")
    await mutation_limit(request, str(principal.id))
    result = await admission.save_platform_policy(
        session, principal, platform_type, payload
    )
    await session.commit()
    return result
