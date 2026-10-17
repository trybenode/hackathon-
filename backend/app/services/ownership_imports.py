"""Unsigned CSV imports with explicit operations ownership review; never writes verified outcomes."""

import csv
from datetime import date, timedelta
from hashlib import sha256
from io import StringIO
import json
from math import ceil
from uuid import UUID
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import get_settings
from app.models.admission import OwnershipImport, ProvisionalRecord, ReviewDecision
from app.models.domain import User, Worker
from app.models.portability import WorkerLink
from app.schemas.admission import DecisionInput, ImportPage, ImportView, ProvisionalView
from app.services.feature_common import FeatureError, now, aware, audit, digest
from app.services.review_access import worker_for, reviewer
from app.services import review_storage

CSV_LIMIT = 2 * 1024 * 1024
ROW_LIMIT = 1000


def enabled() -> None:
    """Uploads/reviews are opt-in and cannot silently consume private files when disabled."""
    if not get_settings().unsigned_imports_enabled:
        raise FeatureError(
            404,
            "UNSIGNED_IMPORTS_DISABLED",
            "Unsigned history imports are not enabled.",
        )


def environment() -> str:
    """Operations review production evidence; sandbox identity never qualifies."""
    return "production"


def view(row: OwnershipImport) -> ImportView:
    """Return owner-visible review state without storage keys or reviewer-only notes."""
    return ImportView(
        id=row.id,
        version=row.version,
        source_name=row.source_name,
        state=(
            "expired"
            if row.state in {"preparing", "submitted", "changes_requested"}
            and aware(row.expires_at) <= now()
            else row.state
        ),
        row_count=len(row.rows),
        document_present=bool(row.document_key),
        expires_at=row.expires_at,
        last_reason=row.last_reason,
        rows=row.rows,
        ownership_label=(
            "Ownership reviewed; history unverified"
            if row.state == "approved"
            else "History unverified"
        ),
    )


async def expire(session: AsyncSession) -> None:
    """Delete expired raw documents; expiry never automatically approves pending evidence."""
    rows = (
        await session.scalars(
            select(OwnershipImport)
            .where(
                OwnershipImport.expires_at <= now(),
                (
                    OwnershipImport.document_key.is_not(None)
                    | OwnershipImport.state.in_(
                        ["preparing", "submitted", "changes_requested"]
                    )
                ),
            )
            .limit(100)
        )
    ).all()
    for candidate in rows:
        # Same lock order as submit/review: a cleanup cannot expire a newly reviewed revision.
        await session.scalar(
            select(Worker).where(Worker.id == candidate.worker_id).with_for_update()
        )
        row = await session.get(
            OwnershipImport, candidate.id, with_for_update=True, populate_existing=True
        )
        if aware(row.expires_at) > now():
            continue
        if row.state in {"preparing", "submitted", "changes_requested"}:
            row.state = "expired"
            row.version += 1
        if row.document_key:
            try:
                await review_storage.delete(row.document_key)
                row.document_key = None
            except FeatureError:
                continue  # Private reads already reject expiry; scheduled cleanup retries deletion.


async def owned(
    session: AsyncSession, user: User, batch_id: UUID, *, lock: bool = False
) -> OwnershipImport:
    """Bind batch operations to the authenticated worker; never trust upload UUIDs."""
    worker = await worker_for(session, user, lock=lock)
    query = select(OwnershipImport).where(
        OwnershipImport.id == batch_id, OwnershipImport.worker_id == worker.id
    )
    row = await session.scalar(query.with_for_update() if lock else query)
    if row is None:
        raise FeatureError(404, "IMPORT_NOT_FOUND", "History import not found.")
    return row


async def parse_rows(
    session: AsyncSession, worker: Worker, data: bytes, source: str
) -> list[dict]:
    """Parse canonical facts and worker bindings without inferring absent evidence."""
    if not data or len(data) > CSV_LIMIT:
        raise FeatureError(422, "CSV_SIZE", "Use a CSV up to 2 MiB.")
    try:
        text = data.decode("utf-8-sig")
        if text.lstrip().startswith(("{", "[")):
            raise FeatureError(
                422,
                "SIGNED_ROUTE_REQUIRED",
                "Credential JSON must use signed import; failed signatures cannot be downgraded.",
            )
        reader = csv.DictReader(StringIO(text), strict=True)
        required = {"worker_id", "job_id", "date", "status"}
        allowed = required | {"cancelled_by", "source_reference"}
        if (
            not reader.fieldnames
            or len(set(reader.fieldnames)) != len(reader.fieldnames)
            or not required <= set(reader.fieldnames)
            or not set(reader.fieldnames) <= allowed
        ):
            raise ValueError("Use the CSV template columns")
        mappings = set()
        if source.startswith("platform:"):
            org = UUID(source.removeprefix("platform:"))
            mappings = set(
                (
                    await session.scalars(
                        select(WorkerLink.external_worker_id).where(
                            WorkerLink.worker_id == worker.id,
                            WorkerLink.organization_id == org,
                        )
                    )
                ).all()
            )
        result, seen = [], set()
        for number, raw in enumerate(reader, 2):
            if number > ROW_LIMIT + 1:
                raise ValueError("At most 1000 rows are allowed")
            if None in raw or any(v is None for v in raw.values()):
                raise ValueError(f"Row {number}: inconsistent columns")
            row = {k: v.strip() for k, v in raw.items()}
            if row["worker_id"] != str(worker.id) and row["worker_id"] not in mappings:
                raise FeatureError(
                    422,
                    "WORKER_MISMATCH",
                    f"Row {number}: document belongs to another or an unmapped worker.",
                )
            if (
                not row["job_id"]
                or len(row["job_id"]) > 100
                or row["job_id"][0] in "=+-@"
            ):
                raise ValueError(f"Row {number}: invalid job identifier")
            if row["status"] not in {"completed", "cancelled", "no_show", "unknown"}:
                raise ValueError(f"Row {number}: unsupported status")
            parsed = date.fromisoformat(row["date"])
            if parsed > now().date():
                raise ValueError(f"Row {number}: date is in the future")
            if row["status"] == "cancelled" and row.get("cancelled_by") not in {
                "worker",
                "client",
                "platform",
            }:
                raise ValueError(f"Row {number}: identify who cancelled the job")
            if len(row.get("source_reference", "")) > 200:
                raise ValueError(f"Row {number}: source reference is too long")
            row["worker_id"] = str(worker.id)
            row["date"] = parsed.isoformat()
            key = row["job_id"]
            if key in seen:
                raise ValueError(f"Row {number}: duplicate job identifier")
            seen.add(key)
            result.append(row)
        if not result:
            raise ValueError("The CSV has no job rows")
        return result
    except FeatureError:
        raise
    except (UnicodeError, ValueError, csv.Error):
        raise FeatureError(
            422,
            "CSV_INVALID",
            "Use the template: valid dates/statuses, one worker, unique job IDs and cancellation attribution.",
        ) from None


async def prepare(
    session: AsyncSession,
    user: User,
    data: bytes,
    source: str,
    operation: UUID,
    replaces: UUID | None = None,
) -> ImportView:
    """Persist an immutable CSV preview with a stable receipt before document upload."""
    enabled()
    worker = await worker_for(session, user, lock=True)
    source = source.strip()
    if not 1 <= len(source) <= 120:
        raise FeatureError(422, "SOURCE_REQUIRED", "Name the source of this history.")
    fingerprint = digest(sha256(data).hexdigest() + source + str(replaces))
    previous = await session.scalar(
        select(OwnershipImport).where(
            OwnershipImport.worker_id == worker.id,
            OwnershipImport.operation_id == operation,
        )
    )
    if previous:
        if previous.payload_hash != fingerprint:
            raise FeatureError(
                409,
                "IDEMPOTENCY_CONFLICT",
                "This operation was used with another file.",
            )
        return view(previous)
    count = await session.scalar(
        select(func.count())
        .select_from(OwnershipImport)
        .where(
            OwnershipImport.worker_id == worker.id,
            OwnershipImport.created_at >= now() - timedelta(days=1),
        )
    )
    if count >= 10:
        raise FeatureError(
            429,
            "IMPORT_LIMIT",
            "At most ten import preparations are allowed per day.",
            3600,
        )
    rows = await parse_rows(session, worker, data, source)
    if replaces:
        old = await owned(session, user, replaces)
        if old.state == "preparing":
            raise FeatureError(
                409,
                "REPLACEMENT_INVALID",
                "Replace a submitted review revision, not a draft.",
            )
    row = OwnershipImport(
        worker_id=worker.id,
        operation_id=operation,
        payload_hash=fingerprint,
        source_name=source,
        rows=rows,
        replaces_id=replaces,
        expires_at=now() + timedelta(days=30),
    )
    session.add(row)
    await session.flush()
    audit(
        session,
        user.id,
        "ownership_import",
        row.id,
        "prepared",
        {"row_count": len(rows)},
    )
    return view(row)


async def attach(
    session: AsyncSession, user: User, batch_id: UUID, data: bytes
) -> ImportView:
    """Attach one immutable, content-hashed supporting document; retries reuse it."""
    enabled()
    row = await owned(session, user, batch_id, lock=True)
    content_hash = sha256(data).hexdigest()
    if row.document_hash:
        if row.document_hash != content_hash:
            raise FeatureError(
                409,
                "DOCUMENT_IMMUTABLE",
                "Create a new import revision to change the document.",
            )
        return view(row)
    if row.state != "preparing" or aware(row.expires_at) <= now():
        raise FeatureError(
            409, "IMPORT_IMMUTABLE", "This import cannot accept another document."
        )
    content_type = review_storage.document_type(data)
    key = await review_storage.store(data, content_type)
    row.document_key, row.document_hash, row.document_type = (
        key,
        content_hash,
        content_type,
    )
    row.version += 1
    try:
        await session.flush()
    except Exception:
        await review_storage.delete(key)
        raise
    return view(row)


def check_version(row: OwnershipImport, version: int) -> None:
    """Reject stale or concurrent writes instead of silently replacing a decision."""
    if row.version != version:
        raise FeatureError(
            409, "STALE_REVISION", "Reload this review before continuing."
        )


async def submit(
    session: AsyncSession, user: User, batch_id: UUID, version: int
) -> ImportView:
    """Submit the exact reviewed upload and deliberately invalidate replaced evidence."""
    enabled()
    row = await owned(session, user, batch_id, lock=True)
    if row.state == "submitted" and version == row.version - 1:
        return view(row)
    check_version(row, version)
    if (
        row.state != "preparing"
        or not row.document_key
        or aware(row.expires_at) <= now()
    ):
        raise FeatureError(
            409, "DOCUMENT_REQUIRED", "Attach a supporting document before submitting."
        )
    duplicate = await session.scalar(
        select(OwnershipImport).where(
            OwnershipImport.worker_id == row.worker_id,
            OwnershipImport.id != row.id,
            OwnershipImport.payload_hash == row.payload_hash,
            OwnershipImport.document_hash == row.document_hash,
            OwnershipImport.state.in_(["submitted", "approved"]),
        )
    )
    if duplicate:
        raise FeatureError(
            409,
            "DUPLICATE_IMPORT",
            f"This evidence is already submitted as {duplicate.id}.",
        )
    if row.replaces_id:
        old = await owned(session, user, row.replaces_id, lock=True)
        old.state = "withdrawn"
        old.version += 1
    row.state = "submitted"
    row.version += 1
    audit(
        session,
        user.id,
        "ownership_import",
        row.id,
        "submitted",
        {"version": row.version},
    )
    return view(row)


async def withdraw(
    session: AsyncSession, user: User, batch_id: UUID, version: int
) -> ImportView:
    """Withdraw evidence immediately from provisional eligibility without deleting audit history."""
    enabled()
    row = await owned(session, user, batch_id, lock=True)
    check_version(row, version)
    row.state = "withdrawn"
    row.version += 1
    audit(session, user.id, "ownership_import", row.id, "withdrawn")
    return view(row)


async def page(
    session: AsyncSession,
    user: User,
    page_number: int,
    size: int,
    *,
    operations: bool = False,
) -> ImportPage:
    """Paginate worker-owned imports or the explicitly authorized operations queue."""
    enabled()
    query = select(OwnershipImport)
    if operations:
        await reviewer(session, user, "operations", environment())
    else:
        worker = await worker_for(session, user)
        query = query.where(OwnershipImport.worker_id == worker.id)
    total = await session.scalar(select(func.count()).select_from(query.subquery()))
    rows = (
        await session.scalars(
            query.order_by(OwnershipImport.created_at.desc(), OwnershipImport.id)
            .offset((page_number - 1) * size)
            .limit(size)
        )
    ).all()
    return ImportPage(
        items=[view(row).model_copy(update={"rows": []}) for row in rows],
        total=total,
        page=page_number,
        size=size,
        pages=ceil(total / size),
    )


async def decide(
    session: AsyncSession, actor: User, batch_id: UUID, payload: DecisionInput
) -> ImportView:
    """Approve only an association reviewed against genuine identity, never job authenticity."""
    enabled()
    await reviewer(session, actor, "operations", environment())
    initial = await session.get(OwnershipImport, batch_id)
    if not initial:
        raise FeatureError(404, "IMPORT_NOT_FOUND", "History import not found.")
    worker = await session.scalar(
        select(Worker).where(Worker.id == initial.worker_id).with_for_update()
    )
    row = await session.get(
        OwnershipImport, batch_id, with_for_update=True, populate_existing=True
    )
    if worker.user_id == actor.id:
        raise FeatureError(403, "SELF_REVIEW", "You cannot review your own evidence.")
    check_version(row, payload.version)
    if row.state not in {"submitted", "changes_requested", "approved"}:
        raise FeatureError(
            409,
            "REVIEW_STATE",
            "This evidence cannot be reviewed in its current state.",
        )
    identity_id = None
    if payload.decision == "approve":
        if (
            row.state != "submitted"
            or not row.document_key
            or aware(row.expires_at) <= now()
        ):
            raise FeatureError(
                409, "DOCUMENT_EXPIRED", "Current submitted evidence is required."
            )
        from app.services.worker_verification import verification_for

        from app.services.worker_record import latest_check

        identity = await latest_check(session, worker.user_id)
        identity_id = identity.id if identity else None
        checks = await verification_for(session, worker)
        if checks.identity != "verified" or not payload.ownership_basis:
            raise FeatureError(
                409,
                "OWNERSHIP_UNRESOLVED",
                "Genuine identity and a documented ownership association are required; names alone are insufficient.",
            )
        for item in row.rows:
            key = digest(row.source_name.casefold() + ":" + item["job_id"])
            fingerprint = digest(json.dumps(item, sort_keys=True))
            previous = await session.scalar(
                select(ProvisionalRecord).where(
                    ProvisionalRecord.worker_id == worker.id,
                    ProvisionalRecord.source_key == key,
                )
            )
            if previous:
                prior_batch = await session.get(OwnershipImport, previous.batch_id)
                if prior_batch.state == "approved":
                    if previous.payload_hash != fingerprint:
                        raise FeatureError(
                            409,
                            "SOURCE_RECORD_CONFLICT",
                            "An approved job has different details; explicitly replace its batch.",
                        )
                    continue
                previous.batch_id, previous.payload_hash, previous.details = (
                    row.id,
                    fingerprint,
                    item,
                )
            else:
                session.add(
                    ProvisionalRecord(
                        worker_id=worker.id,
                        batch_id=row.id,
                        source_key=key,
                        payload_hash=fingerprint,
                        details=item,
                    )
                )
        row.state = "approved"
    elif payload.decision == "request_information":
        row.state = "changes_requested"
    elif payload.decision in {"decline", "revoke"}:
        row.state = "rejected"
    else:
        raise FeatureError(
            422, "REVIEW_DECISION", "Ownership review does not grant onboarding access."
        )
    row.last_reason = payload.reason
    row.version += 1
    if row.state in {"approved", "rejected"}:
        row.expires_at = now() + timedelta(days=30)
    session.add(
        ReviewDecision(
            actor_id=actor.id,
            entity_type="ownership_import",
            entity_id=row.id,
            version=row.version,
            decision=payload.decision,
            reason=payload.reason
            + (
                "\nOwnership basis: " + payload.ownership_basis
                if payload.ownership_basis
                else ""
            ),
            evidence_revision=digest(
                row.payload_hash + (row.document_hash or "") + str(identity_id)
            ),
        )
    )
    audit(
        session,
        actor.id,
        "ownership_import",
        row.id,
        "reviewed",
        {
            "decision": payload.decision,
            "version": row.version,
            "identity_check_id": str(identity_id) if identity_id else None,
        },
    )
    await session.flush()
    return view(row)


async def provisional(session: AsyncSession, worker_id: UUID) -> ProvisionalView:
    """Only reviewed unverified rows influence a separate capped starting-history rating."""
    if not get_settings().unsigned_imports_enabled:
        return ProvisionalView(rating=None, count=0)
    rows = (
        await session.scalars(
            select(ProvisionalRecord)
            .join(OwnershipImport, OwnershipImport.id == ProvisionalRecord.batch_id)
            .where(
                ProvisionalRecord.worker_id == worker_id,
                OwnershipImport.state == "approved",
            )
        )
    ).all()
    worker = await session.get(Worker, worker_id)
    from app.services.worker_verification import verification_for

    if not worker or (await verification_for(session, worker)).identity != "verified":
        return ProvisionalView(rating=None, count=0)
    facts = [
        r.details
        for r in rows
        if r.details["status"] in {"completed", "no_show", "cancelled"}
        and not (
            r.details["status"] == "cancelled"
            and r.details.get("cancelled_by") != "worker"
        )
    ]
    if not facts:
        return ProvisionalView(rating=None, count=len(rows))
    from app.services.trust_scoring.scoring import starting_rating

    signals = {
        "completion_rate": sum(x["status"] == "completed" for x in facts) / len(facts),
        "cancellation_rate": sum(x["status"] == "cancelled" for x in facts)
        / len(facts),
    }
    result = starting_rating(signals, len(facts))
    return ProvisionalView(rating=min(result["starting_rating"], 0.65), count=len(rows))


async def expire_orphans(session: AsyncSession) -> int:
    """Remove attachments older than 30 days whose database write never committed."""
    cutoff = now() - timedelta(days=30)
    deleted = 0
    async for objects in review_storage.object_pages():
        candidates = [key for key, modified in objects if aware(modified) <= cutoff]
        if not candidates:
            continue
        referenced = set(
            (
                await session.scalars(
                    select(OwnershipImport.document_key).where(
                        OwnershipImport.document_key.in_(candidates)
                    )
                )
            ).all()
        )
        for key in candidates:
            if key in referenced:
                continue
            try:
                await review_storage.delete(key)
                deleted += 1
            except FeatureError:
                continue
    return deleted
