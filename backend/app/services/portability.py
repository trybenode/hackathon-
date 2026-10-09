"""Worker-owned records and expiring public/platform consent grants."""
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from math import ceil
import secrets
import json
import re
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.domain import AuditEvent, NormalizedOutcome, Organization, User, Worker
from app.services.worker_record import WorkerRecord as RecordSnapshot, load_record, completion_labels
from app.services.trust_scoring.evidence import scoring_inputs
from app.models.portability import PlatformGrant, PlatformKey, ShareGrant
from app.schemas.portability import EvidenceAssessment, GrantList, GrantResponse, HistoryItem, HistoryPage, IdentitySummary, VerificationSummary, WorkerRecord


class FeatureError(Exception):
    """Expected domain failure with a stable HTTP-facing code."""
    def __init__(self, status: int, code: str, detail: str, retry_after: int | None = None) -> None:
        self.status, self.code, self.detail, self.retry_after = status, code, detail, retry_after
        super().__init__(detail)


def now() -> datetime:
    """Return the clock used by expiring grants and review windows."""
    return datetime.now(UTC)


def aware(value: datetime) -> datetime:
    """Normalize SQLite timestamps without changing Postgres timestamps."""
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def digest(value: str) -> str:
    """Hash random bearer credentials before persistence."""
    return sha256(value.encode()).hexdigest()


def general_area(location: str | None) -> str | None:
    """Publish a Nigerian state/territory only, never an unstructured address."""
    if not location:
        return None
    areas = ("Abia", "Adamawa", "Akwa Ibom", "Anambra", "Bauchi", "Bayelsa", "Benue", "Borno",
        "Cross River", "Delta", "Ebonyi", "Edo", "Ekiti", "Enugu", "Gombe", "Imo", "Jigawa",
        "Kaduna", "Kano", "Katsina", "Kebbi", "Kogi", "Kwara", "Lagos", "Nasarawa", "Niger",
        "Ogun", "Ondo", "Osun", "Oyo", "Plateau", "Rivers", "Sokoto", "Taraba", "Yobe", "Zamfara")
    if re.search(r"\b(?:Abuja|FCT)\b", location, re.IGNORECASE):
        return "FCT"
    for area in areas:
        if re.search(r"\b" + re.escape(area) + r"\b", location, re.IGNORECASE):
            return area
    return None


def audit(session: AsyncSession, actor_id: UUID | None, entity_type: str, entity_id: UUID, action: str, metadata: dict | None = None) -> None:
    """Record meaningful changes without bearer tokens or private comments."""
    session.add(AuditEvent(actor_id=actor_id, entity_type=entity_type, entity_id=entity_id, action=action, event_metadata=metadata or {}))


async def own_worker(session: AsyncSession, user: User) -> Worker:
    """Resolve an active user's worker record; never trust a caller's UUID."""
    worker = await session.scalar(select(Worker).where(Worker.user_id == user.id))
    if not user.is_active or worker is None:
        raise FeatureError(404, "WORKER_NOT_FOUND", "No worker record is linked to this account.")
    return worker


def history_item(row: NormalizedOutcome, source_name: str | None = None) -> HistoryItem:
    """Expose work facts and provenance, excluding client identifiers/evidence URLs."""
    return HistoryItem(outcome_id=row.id, source_record_id=row.outcome_key, source_platform=row.source_platform, source_name=source_name,
        occurred_at=row.occurred_at, status=row.status.value, rating=float(row.rating) if row.rating is not None else None,
        verified=row.verified, verification_method=row.verification_method, verified_by_org_id=row.verified_by_org_id,
        verified_at=row.verified_at, available_signals=row.available_signals)


async def history_items(session: AsyncSession, rows: list[NormalizedOutcome]) -> list[HistoryItem]:
    """Resolve human-readable source names in one bounded query per history page."""
    source_ids = {}
    for row in rows:
        if row.source_platform.startswith("platform:"):
            try:
                source_ids[row.source_platform] = UUID(row.source_platform.removeprefix("platform:"))
            except ValueError:
                continue
    names = {}
    if source_ids:
        organizations = (await session.scalars(select(Organization).where(Organization.id.in_(source_ids.values())))).all()
        names = {org.id: org.name for org in organizations}
    labels = await completion_labels(session, rows)
    inputs = await scoring_inputs(session, rows)
    return [history_item(row, names.get(source_ids.get(row.source_platform))).model_copy(update={"completion_status": labels[row.id], "status": evidence["status"], "available_signals": evidence["available_signals"]}) for row, evidence in zip(rows, inputs, strict=True)]


def summary_from_record(record: RecordSnapshot) -> VerificationSummary:
    """Explicit public whitelist; private score, names and history stay private."""
    parts = record.name.split()
    name = parts[0] + (f" {parts[-1][0]}." if len(parts) > 1 else "") if parts else "Worker"
    return VerificationSummary(display_name=name, role=record.role, location=general_area(record.location), identity=IdentitySummary(status=record.identity_status),
        assessment=EvidenceAssessment(decision=record.decision, band=record.band, confidence=float(record.confidence), status=record.status, explanation_summary=record.explanation_summary, signals_used=record.signals_used, assessed_at=record.assessed_at),
        verified_outcomes=record.verified_outcomes, self_declared_outcomes=record.self_declared_outcomes, completed_jobs=record.completed_jobs, completion_rate=record.completion_rate,
        active_guarantor=bool(record.guarantor and record.guarantor.status == "Active" and (record.guarantor.verified or record.guarantor.sandbox)), guarantor_sandbox=bool(record.guarantor and record.guarantor.status == "Active" and record.guarantor.sandbox), updated_at=record.last_updated)


async def worker_record(session: AsyncSession, worker: Worker, *, page: int = 1, size: int = 20) -> WorkerRecord:
    """Compatibility projection of the canonical worker snapshot."""
    user = await session.get(User, worker.user_id)
    snapshot = await load_record(session, user, include_history=False)
    rows = list((await session.scalars(select(NormalizedOutcome).where(NormalizedOutcome.worker_id == worker.id).order_by(NormalizedOutcome.occurred_at.desc(), NormalizedOutcome.id).offset((page-1)*size).limit(size))).all())
    return WorkerRecord(**summary_from_record(snapshot).model_dump(), worker_id=worker.id, outcomes=await history_items(session, rows), total_outcomes=snapshot.total_outcomes, starting_rating=snapshot.starting_rating, starting_rating_label=snapshot.starting_rating_label)


async def issue_grant(session: AsyncSession, user: User, *, organization_id: UUID | None = None, permissions: list[str] | None = None, operation_id: UUID | None = None) -> GrantResponse:
    """Issue a seven-day grant; disclose its random token only once."""
    worker = await own_worker(session, user)
    await session.execute(select(Worker.id).where(Worker.id == worker.id).with_for_update())
    model = ShareGrant if organization_id is None else PlatformGrant
    payload_hash = digest(json.dumps({"organization_id": str(organization_id) if organization_id else None, "permissions": sorted(set(permissions or []))}, sort_keys=True))
    if operation_id is not None:
        existing = await session.scalar(select(model).where(model.worker_id == worker.id, model.operation_id == operation_id))
        if existing is not None:
            if existing.payload_hash != payload_hash:
                raise FeatureError(409, "IDEMPOTENCY_CONFLICT", "This operation identifier was already used with different approval details.")
            organization = await session.get(Organization, organization_id) if organization_id else None
            return grant_response(existing, organization_name=organization.name if organization else None)
    organization = None
    if organization_id is not None:
        organization = await session.get(Organization, organization_id)
        enabled = await session.scalar(select(PlatformKey.id).where(PlatformKey.organization_id == organization_id, PlatformKey.revoked_at.is_(None)))
        if not organization or not enabled:
            raise FeatureError(404, "PLATFORM_NOT_FOUND", "This platform is not available for consent.")
    token = secrets.token_urlsafe(32)
    fields = dict(worker_id=worker.id, operation_id=operation_id, payload_hash=payload_hash, token_hash=digest(token), expires_at=now()+timedelta(days=7))
    grant = ShareGrant(**fields) if organization is None else PlatformGrant(**fields, organization_id=organization.id, permissions=sorted(set(permissions or [])))
    session.add(grant)
    await session.flush()
    audit(session, user.id, "share_grant" if organization is None else "platform_grant", grant.id, "issued")
    return grant_response(grant, token=token, organization_name=organization.name if organization else None)


def grant_response(grant: ShareGrant | PlatformGrant, *, token: str | None = None, organization_name: str | None = None) -> GrantResponse:
    """Return metadata without retaining or recovering a bearer token."""
    return GrantResponse(operation_id=grant.operation_id, id=grant.id, created_at=grant.created_at, expires_at=grant.expires_at, revoked_at=grant.revoked_at,
        token=token, organization_id=getattr(grant, "organization_id", None), organization_name=organization_name,
        permissions=getattr(grant, "permissions", None))


async def list_grants(session: AsyncSession, user: User, model: type[ShareGrant] | type[PlatformGrant], page: int, size: int) -> GrantList:
    """Paginate only this worker's grants, excluding bearer secrets."""
    worker = await own_worker(session, user)
    total = await session.scalar(select(func.count()).select_from(model).where(model.worker_id == worker.id))
    rows = (await session.scalars(select(model).where(model.worker_id == worker.id).order_by(model.created_at.desc(), model.id)
        .offset((page-1)*size).limit(size))).all()
    items = []
    for row in rows:
        org = await session.get(Organization, row.organization_id) if isinstance(row, PlatformGrant) else None
        items.append(grant_response(row, organization_name=org.name if org else None))
    return GrantList(items=items, total=total, page=page, size=size, pages=ceil(total/size))


async def revoke_grant(session: AsyncSession, user: User, model: type[ShareGrant] | type[PlatformGrant], grant_id: UUID) -> None:
    """Idempotently revoke an owned grant, leaving its audit history intact."""
    worker = await own_worker(session, user)
    grant = await session.scalar(select(model).where(model.id == grant_id, model.worker_id == worker.id).with_for_update())
    if grant is None:
        raise FeatureError(404, "GRANT_NOT_FOUND", "Grant not found.")
    if grant.revoked_at is None:
        grant.revoked_at = now()
        audit(session, user.id, model.__tablename__, grant.id, "revoked")


async def public_summary(session: AsyncSession, token: str) -> VerificationSummary:
    """Read a live standard summary; a public link never grants detailed history."""
    if not 32 <= len(token) <= 128:
        raise FeatureError(404, "LINK_NOT_FOUND", "Verification link not found.")
    grant = await session.scalar(select(ShareGrant).where(ShareGrant.token_hash == digest(token)))
    if grant is None:
        raise FeatureError(404, "LINK_NOT_FOUND", "Verification link not found.")
    if grant.revoked_at is not None or aware(grant.expires_at) <= now():
        raise FeatureError(410, "LINK_UNAVAILABLE", "This link has expired or been revoked.")
    worker = await session.get(Worker, grant.worker_id)
    if worker is None:
        raise FeatureError(404, "WORKER_NOT_FOUND", "Worker record is unavailable.")
    user = await session.get(User, worker.user_id)
    if user is None or not user.is_active:
        raise FeatureError(404, "WORKER_NOT_FOUND", "Worker record is unavailable.")
    return summary_from_record(await load_record(session, user, include_history=False, include_starting_history=False))


async def grant_operation(session: AsyncSession, user: User, model: type[ShareGrant] | type[PlatformGrant], operation_id: UUID) -> GrantResponse:
    """Reconcile an owned operation; hashes cannot recover the returned secret."""
    worker = await own_worker(session, user)
    grant = await session.scalar(select(model).where(model.worker_id == worker.id, model.operation_id == operation_id))
    if grant is None:
        raise FeatureError(404, "OPERATION_NOT_FOUND", "This operation has not completed. Retry using the same identifier.")
    organization = await session.get(Organization, grant.organization_id) if isinstance(grant, PlatformGrant) else None
    return grant_response(grant, organization_name=organization.name if organization else None)


async def own_history(session: AsyncSession, user: User, page: int, size: int) -> HistoryPage:
    """Paginate every outcome belonging to the signed-in worker."""
    worker = await own_worker(session, user)
    total = await session.scalar(select(func.count()).select_from(NormalizedOutcome).where(NormalizedOutcome.worker_id == worker.id))
    rows = list((await session.scalars(select(NormalizedOutcome).where(NormalizedOutcome.worker_id == worker.id).order_by(NormalizedOutcome.occurred_at.desc(), NormalizedOutcome.id).offset((page-1)*size).limit(size))).all())
    return HistoryPage(items=await history_items(session, rows), total=total, page=page, size=size, pages=ceil(total/size))
