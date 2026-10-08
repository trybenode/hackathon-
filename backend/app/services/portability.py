"""Worker-owned records and expiring public/platform consent grants."""
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from math import ceil
import secrets
import re
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.domain import AgreementStatus, AuditEvent, GuarantorAgreement, IdentityVerification, NormalizedOutcome, Organization, TrustAssessment, User, Worker
from app.models.portability import PlatformGrant, PlatformKey, ShareGrant
from app.schemas.portability import EvidenceAssessment, GrantList, GrantResponse, HistoryItem, IdentitySummary, VerificationSummary, WorkerRecord
from app.services.normalisation import normalise_db_row
from app.services.trust_scoring.assessment import assess_worker
from app.services.trust_scoring.scoring import starting_rating
from app.services.trust_scoring.signals import aggregate


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
    return [history_item(row, names.get(source_ids.get(row.source_platform))) for row in rows]


async def worker_record(session: AsyncSession, worker: Worker, *, page: int = 1, size: int = 20) -> WorkerRecord:
    """Build current private/public evidence using the shared assessment service."""
    # Serialize mutations/assessment refreshes for this worker across endpoints.
    await session.execute(select(Worker.id).where(Worker.id == worker.id).with_for_update())
    result = await assess_worker(session, worker.id, "generic")
    assessment_row = await session.get(TrustAssessment, result.id)
    user = await session.get(User, worker.user_id)
    if user is None or not user.is_active:
        raise FeatureError(404, "WORKER_NOT_FOUND", "Worker record is unavailable.")
    counts = (await session.execute(select(func.count(NormalizedOutcome.id),
        func.count(NormalizedOutcome.id).filter(NormalizedOutcome.verified.is_(True)),
        func.count(NormalizedOutcome.id).filter(NormalizedOutcome.verified.is_(True), NormalizedOutcome.status == "COMPLETED")
        ).where(NormalizedOutcome.worker_id == worker.id))).one()
    total, verified, completed = counts
    rows = list((await session.scalars(select(NormalizedOutcome).where(NormalizedOutcome.worker_id == worker.id)
        .order_by(NormalizedOutcome.occurred_at.desc(), NormalizedOutcome.id).offset((page-1)*size).limit(size))).all())
    identity = await session.scalar(select(IdentityVerification).where(IdentityVerification.user_id == user.id,
        IdentityVerification.check_type == "identity").order_by(IdentityVerification.created_at.desc(), IdentityVerification.id.desc()).limit(1))
    identity_status = "not_verified"
    if identity and identity.status == "verified":
        identity_status = "sandbox" if identity.provider == "stub" else "verified"
    guarantors = list((await session.scalars(select(GuarantorAgreement).where(GuarantorAgreement.worker_id == worker.id,
        GuarantorAgreement.status == AgreementStatus.ACTIVE, GuarantorAgreement.valid_until > now()))).all())
    guarantor_sandbox = False
    for guarantor in guarantors:
        check = await session.scalar(select(IdentityVerification).where(IdentityVerification.user_id == guarantor.guarantor_user_id,
            IdentityVerification.check_type == "identity").order_by(IdentityVerification.created_at.desc()).limit(1))
        guarantor_sandbox = guarantor_sandbox or check is None or check.provider == "stub" or check.status != "verified"
    imported = list((await session.scalars(select(NormalizedOutcome).where(NormalizedOutcome.worker_id == worker.id,
        NormalizedOutcome.verified.is_(False)))).all())
    initial = None
    if imported:
        signals, n = aggregate([normalise_db_row(r) for r in imported], {"completion_rate", "cancellation_rate"})
        initial = starting_rating(signals, n)
    parts = user.display_name.split()
    short_name = parts[0] + (f" {parts[-1][0]}." if len(parts) > 1 else "") if parts else "Worker"
    return WorkerRecord(worker_id=worker.id, display_name=short_name, role=worker.role, location=general_area(worker.location),
        identity=IdentitySummary(status=identity_status),
        assessment=EvidenceAssessment(decision=result.decision, band=result.band, confidence=float(result.confidence),
            status=result.status, explanation_summary=result.explanation_summary, signals_used=result.signals_used,
            assessed_at=assessment_row.assessed_at),
        verified_outcomes=verified, self_declared_outcomes=total-verified, completed_jobs=completed,
        completion_rate=completed/verified if verified else None, active_guarantor=bool(guarantors), guarantor_sandbox=guarantor_sandbox,
        updated_at=now(), outcomes=await history_items(session, rows), total_outcomes=total,
        starting_rating=initial["starting_rating"] if initial else None, starting_rating_label=initial["label"] if initial else None)


async def issue_grant(session: AsyncSession, user: User, *, organization_id: UUID | None = None, permissions: list[str] | None = None) -> GrantResponse:
    """Issue a seven-day grant; disclose its random token only once."""
    worker = await own_worker(session, user)
    organization = None
    if organization_id is not None:
        organization = await session.get(Organization, organization_id)
        enabled = await session.scalar(select(PlatformKey.id).where(PlatformKey.organization_id == organization_id, PlatformKey.revoked_at.is_(None)))
        if not organization or not enabled:
            raise FeatureError(404, "PLATFORM_NOT_FOUND", "This platform is not available for consent.")
    token = secrets.token_urlsafe(32)
    fields = dict(worker_id=worker.id, token_hash=digest(token), expires_at=now()+timedelta(days=7))
    grant = ShareGrant(**fields) if organization is None else PlatformGrant(**fields, organization_id=organization.id, permissions=sorted(set(permissions or [])))
    session.add(grant)
    await session.flush()
    audit(session, user.id, "share_grant" if organization is None else "platform_grant", grant.id, "issued")
    return grant_response(grant, token=token, organization_name=organization.name if organization else None)


def grant_response(grant: ShareGrant | PlatformGrant, *, token: str | None = None, organization_name: str | None = None) -> GrantResponse:
    """Return metadata without retaining or recovering a bearer token."""
    return GrantResponse(id=grant.id, created_at=grant.created_at, expires_at=grant.expires_at, revoked_at=grant.revoked_at,
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
    record = await worker_record(session, worker)
    return VerificationSummary.model_validate(record.model_dump(include=set(VerificationSummary.model_fields)))
