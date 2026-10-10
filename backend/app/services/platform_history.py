"""Consent-backed platform identity links and provenance-preserving history exchange."""
from math import ceil
from uuid import UUID
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.domain import NormalizedOutcome, Organization, OutcomeSource, OutcomeStatus, RawOutcome, Worker
from app.models.portability import HistoryIdentity, ImportReceipt, PlatformGrant, PlatformKey, WorkerLink
from app.schemas.portability import HistoryImportRequest, HistoryImportResponse, HistoryPage, WorkerLinkResponse
from app.services.portability import FeatureError, audit, aware, digest, history_items, now


async def active_grant(session: AsyncSession, grant_id: UUID, principal: PlatformKey, permission: str | None = None) -> PlatformGrant:
    """Recheck tenant, expiry and revocation on every request, not just linking."""
    grant = await session.get(PlatformGrant, grant_id)
    if grant is None or grant.organization_id != principal.organization_id:
        raise FeatureError(403, "CONSENT_REQUIRED", "Worker approval is required for this platform.")
    if grant.revoked_at is not None or aware(grant.expires_at) <= now():
        raise FeatureError(403, "CONSENT_EXPIRED", "Worker approval has expired or been revoked.")
    if permission and permission not in grant.permissions:
        raise FeatureError(403, "CONSENT_REQUIRED", f"Worker approval for {permission} is required.")
    return grant


async def link_worker(session: AsyncSession, principal: PlatformKey, external_id: str, token: str) -> WorkerLinkResponse:
    """Consume consent for one tenant/external account; never match by personal data."""
    # Also serialize competing grants for a previously unseen external account.
    await session.execute(select(Organization.id).where(Organization.id == principal.organization_id).with_for_update())
    grant = await session.scalar(select(PlatformGrant).where(PlatformGrant.token_hash == digest(token)).with_for_update())
    if grant is None:
        raise FeatureError(403, "CONSENT_REQUIRED", "Worker approval is required.")
    await active_grant(session, grant.id, principal)
    other = await session.scalar(select(WorkerLink).where(WorkerLink.grant_id == grant.id))
    if other and other.external_worker_id != external_id:
        raise FeatureError(409, "GRANT_ALREADY_LINKED", "This approval is already bound to a different account.")
    link = await session.scalar(select(WorkerLink).where(WorkerLink.organization_id == principal.organization_id,
        WorkerLink.external_worker_id == external_id).with_for_update())
    if link and link.worker_id != grant.worker_id:
        raise FeatureError(409, "WORKER_LINK_CONFLICT", "This platform account is linked to another worker.")
    if link is None:
        link = WorkerLink(organization_id=principal.organization_id, worker_id=grant.worker_id, external_worker_id=external_id, grant_id=grant.id)
        session.add(link)
    else:
        link.grant_id = grant.id
    await session.flush()
    audit(session, None, "worker_link", link.id, "linked", {"organization_id": str(principal.organization_id)})
    return WorkerLinkResponse(worker_id=grant.worker_id, external_worker_id=external_id, expires_at=grant.expires_at)


async def authorized_link(session: AsyncSession, principal: PlatformKey, external_id: str, permission: str) -> WorkerLink:
    """Resolve an opaque external ID within the authenticated platform only."""
    link = await session.scalar(select(WorkerLink).where(WorkerLink.organization_id == principal.organization_id,
        WorkerLink.external_worker_id == external_id))
    if link is None:
        raise FeatureError(404, "WORKER_LINK_NOT_FOUND", "No approved worker link exists for this account.")
    await active_grant(session, link.grant_id, principal, permission)
    return link


async def authorize_assessment(session: AsyncSession, principal: PlatformKey, worker_id: UUID) -> None:
    """Require current read consent for assessments addressed by canonical UUID."""
    links = (await session.scalars(select(WorkerLink).where(WorkerLink.organization_id == principal.organization_id,
        WorkerLink.worker_id == worker_id))).all()
    for link in links:
        try:
            await active_grant(session, link.grant_id, principal, "read_history")
            return
        except FeatureError:
            continue
    raise FeatureError(403, "CONSENT_REQUIRED", "Current worker approval is required for this assessment.")


async def read_history(session: AsyncSession, principal: PlatformKey, external_id: str, page: int, size: int) -> HistoryPage:
    """Return approved facts/provenance with bounded pages, without client PII."""
    link = await authorized_link(session, principal, external_id, "read_history")
    query = select(NormalizedOutcome).where(NormalizedOutcome.worker_id == link.worker_id)
    total = await session.scalar(select(func.count()).select_from(NormalizedOutcome).where(NormalizedOutcome.worker_id == link.worker_id))
    rows = (await session.scalars(query.order_by(NormalizedOutcome.occurred_at.desc(), NormalizedOutcome.id)
        .offset((page-1)*size).limit(size))).all()
    return HistoryPage(items=await history_items(session, list(rows)), total=total, page=page, size=size, pages=ceil(total/size))


async def import_history(session: AsyncSession, principal: PlatformKey, external_id: str, payload: HistoryImportRequest, key: str) -> HistoryImportResponse:
    """Atomically ingest a batch; authenticate provenance without inventing verification."""
    link = await authorized_link(session, principal, external_id, "import_history")
    # Serialize receipts and source initialization across all requests for this tenant.
    await session.execute(select(Organization.id).where(Organization.id == principal.organization_id).with_for_update())
    await session.execute(select(Worker.id).where(Worker.id == link.worker_id).with_for_update())
    await active_grant(session, link.grant_id, principal, "import_history")
    # Explicit null (known absence) differs from an omitted/unknown signal.
    body_hash = digest(payload.model_dump_json(exclude_unset=True))
    receipt = await session.scalar(select(ImportReceipt).where(ImportReceipt.organization_id == principal.organization_id,
        ImportReceipt.idempotency_key == key))
    if receipt:
        if receipt.worker_id != link.worker_id or receipt.payload_hash != body_hash:
            raise FeatureError(409, "IDEMPOTENCY_CONFLICT", "This key was used with a different worker or payload.")
        return HistoryImportResponse.model_validate(receipt.result)
    if any(o.attest for o in payload.outcomes) and not principal.can_attest:
        raise FeatureError(403, "ATTESTATION_NOT_ALLOWED", "This platform has not been approved to attest its own work records.")
    name = f"platform:{principal.organization_id}:worker:{link.worker_id}"
    source = await session.scalar(select(OutcomeSource).where(OutcomeSource.name == name))
    if source is None:
        source = OutcomeSource(name=name, organization_id=principal.organization_id, normalization_version="platform-v1")
        session.add(source)
        await session.flush()
    imported = duplicates = verified = 0
    for item in payload.outcomes:
        item_hash = digest(item.model_dump_json(exclude_unset=True))
        identity = await session.scalar(select(HistoryIdentity).where(HistoryIdentity.worker_id == link.worker_id,
            HistoryIdentity.organization_id == principal.organization_id, HistoryIdentity.source_record_id == item.source_record_id))
        if identity:
            if identity.payload_hash != item_hash:
                raise FeatureError(409, "SOURCE_RECORD_CONFLICT", "An existing source record has different facts. Request a correction rather than replacing it.")
            duplicates += 1
            continue
        raw = RawOutcome(source_id=source.id, external_outcome_id=item.source_record_id,
            payload=item.model_dump(mode="json", exclude_unset=True), payload_checksum=item_hash)
        session.add(raw)
        await session.flush()
        signals = ["completion_rate", "no_show_rate"]
        if "dispute_resolution" in item.model_fields_set:
            signals.append("dispute_rate")
        if item.cancelled_by or item.status != "cancelled":
            signals.append("cancellation_rate")
        if item.client_id:
            signals.append("repeat_hire_rate")
        if item.rating is not None:
            signals.append("average_rating")
        if item.flags is not None:
            signals.extend(["safety_incident_rate", "rework_rate", "damage_report_rate"])
        row = NormalizedOutcome(worker_id=link.worker_id, raw_outcome_id=raw.id, outcome_key=item.source_record_id,
            status=OutcomeStatus(item.status), occurred_at=item.occurred_at, rating=item.rating,
            cancelled_by=item.cancelled_by, dispute_resolution=item.dispute_resolution,
            client_id=digest(f"{principal.organization_id}:{item.client_id}") if item.client_id else None,
            quality_flags=item.flags or [], source_platform=f"platform:{principal.organization_id}",
            import_method="api", normalization_version="platform-v1", verified=item.attest,
            available_signals=signals, verification_method="platform_attested" if item.attest else "self_declared",
            verified_by_org_id=principal.organization_id if item.attest else None, verified_at=now() if item.attest else None)
        session.add(row)
        await session.flush()
        session.add(HistoryIdentity(worker_id=link.worker_id, organization_id=principal.organization_id,
            source_record_id=item.source_record_id, payload_hash=item_hash, outcome_id=row.id))
        await session.flush()
        imported += 1
        verified += int(item.attest)
    result = HistoryImportResponse(imported_outcomes=imported, duplicate_outcomes=duplicates, verified_outcomes=verified)
    session.add(ImportReceipt(organization_id=principal.organization_id, worker_id=link.worker_id,
        idempotency_key=key, payload_hash=body_hash, result=result.model_dump()))
    audit(session, None, "worker", link.worker_id, "history_imported", {"organization_id": str(principal.organization_id), **result.model_dump()})
    return result
