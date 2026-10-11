"""Revisioned declarations, live authorization and atomic respondent receipts."""
from datetime import timedelta
from math import ceil
import hmac
import secrets
from uuid import UUID
from sqlalchemy import func, select, update, or_
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import get_settings
from app.models.domain import Job, JobStatus, User, Worker
from app.models.history import HistoryClaim, ConfirmationRequest, CustomerResponse
from app.schemas.history import ClaimCreate, ClaimEdit, ClaimPage, ClaimView, CustomerDecision, InformalHistoryCounts, RequestCreate, RequestView, RequestPage, ResponseReceipt
from app.services.contact_provider import contact_provider
from app.services.feature_common import FeatureError, audit, aware, digest, now, own_worker


def receipt(row: CustomerResponse) -> ResponseReceipt:
    """Expose only response facts and their evidence method."""
    return ResponseReceipt(declares_customer=row.declares_customer, id=row.id, decision=row.decision, attribution=row.attribution, sandbox=row.sandbox, submitted_at=row.created_at, withdrawn_at=row.withdrawn_at)


async def lock_worker(session: AsyncSession, user: User) -> Worker:
    """Serialize worker-scoped writes and idempotency lookups."""
    worker = await own_worker(session, user)
    await session.execute(select(Worker.id).where(Worker.id == worker.id).with_for_update())
    return worker


async def owned_claim(session: AsyncSession, user: User, claim_id: UUID, *, lock: bool = False) -> HistoryClaim:
    """Fetch a claim belonging to the active worker, without leaking other owners."""
    worker = await (lock_worker(session, user) if lock else own_worker(session, user))
    query = select(HistoryClaim).where(HistoryClaim.id == claim_id, HistoryClaim.worker_id == worker.id)
    row = await session.scalar(query.with_for_update() if lock else query)
    if row is None:
        raise FeatureError(404, "CLAIM_NOT_FOUND", "Work history was not found.")
    return row


async def claim_view(session: AsyncSession, row: HistoryClaim) -> ClaimView:
    """Show only the most recent current-revision response to the worker."""
    response = await session.scalar(select(CustomerResponse).join(ConfirmationRequest).where(ConfirmationRequest.claim_id == row.id, ConfirmationRequest.revision == row.revision).order_by(CustomerResponse.created_at.desc()).limit(1))
    if response and row.job_id:
        request = await session.get(ConfirmationRequest, response.request_id)
        job = await session.get(Job, row.job_id, populate_existing=True)
        if job is None or job.client_id != response.actor_id or request.hiring_customer_id != response.actor_id:
            response = None
    return ClaimView(id=row.id, job_id=row.job_id, revision=row.revision, details=row.details, created_at=row.created_at, archived_at=row.archived_at, response=receipt(response) if response else None)


async def create_claim(session: AsyncSession, user: User, payload: ClaimCreate, operation: UUID) -> ClaimView:
    """Create unscored history; matching retries never create another claim."""
    worker = await lock_worker(session, user)
    fingerprint = digest(payload.model_dump_json())
    previous = await session.scalar(select(HistoryClaim).where(HistoryClaim.worker_id == worker.id, HistoryClaim.operation_id == operation))
    if previous:
        if previous.payload_hash != fingerprint:
            raise FeatureError(409, "IDEMPOTENCY_CONFLICT", "This operation was used with different details.")
        return await claim_view(session, previous)
    details = payload.details.model_dump()
    if payload.job_id:
        job = await session.get(Job, payload.job_id)
        if job is None or job.worker_id != worker.id:
            raise FeatureError(404, "JOB_NOT_FOUND", "No owned job is available.")
        if job.status not in (JobStatus.COMPLETED, JobStatus.RELEASED):
            raise FeatureError(403, "JOB_INCOMPLETE", "Select a completed or released job.")
        if job.client_id is None:
            raise FeatureError(409, "CUSTOMER_UNATTRIBUTED", "The hiring customer has not been attributed.")
        if await session.scalar(select(HistoryClaim.id).where(HistoryClaim.worker_id == worker.id, HistoryClaim.job_id == job.id)):
            raise FeatureError(409, "JOB_ALREADY_RECORDED", "This job already has a history annotation.")
        details["work_type"] = job.title
        details["claimed_completed"] = True
        details["date_text"] = None
    row = HistoryClaim(worker_id=worker.id, job_id=payload.job_id, operation_id=operation, payload_hash=fingerprint, details=details)
    session.add(row)
    await session.flush()
    audit(session, user.id, "history_claim", row.id, "created")
    return await claim_view(session, row)


async def edit_claim(session: AsyncSession, user: User, claim_id: UUID, payload: ClaimEdit) -> ClaimView:
    """Revision edits revoke outstanding recipient access and invalidate old evidence."""
    row = await owned_claim(session, user, claim_id, lock=True)
    if row.archived_at or row.revision != payload.revision:
        raise FeatureError(409, "CLAIM_REVISION_CHANGED", "Reload the latest claim before editing.")
    details = payload.details.model_dump()
    if row.job_id:
        details.update(work_type=row.details["work_type"], claimed_completed=row.details["claimed_completed"], date_text=row.details.get("date_text"))
    row.details = details
    row.revision += 1
    await revoke_claim_requests(session, row.id)
    audit(session, user.id, "history_claim", row.id, "edited", {"revision": row.revision})
    await session.flush()
    return await claim_view(session, row)


async def revoke_claim_requests(session: AsyncSession, claim_id: UUID) -> None:
    """Revoke capabilities in the same transaction as a claim mutation."""
    await session.execute(update(ConfirmationRequest).where(ConfirmationRequest.claim_id == claim_id, ConfirmationRequest.revoked_at.is_(None)).values(revoked_at=now(), session_hash=None))


async def archive_claim(session: AsyncSession, user: User, claim_id: UUID) -> None:
    """Archive without rewriting outcomes, assessments or response audit history."""
    row = await owned_claim(session, user, claim_id, lock=True)
    if row.archived_at is None:
        row.archived_at = now()
        await revoke_claim_requests(session, row.id)
        audit(session, user.id, "history_claim", row.id, "archived")


async def claims(session: AsyncSession, user: User, page: int, size: int) -> ClaimPage:
    """Paginate active declarations independently of normalized outcome history."""
    worker = await own_worker(session, user)
    where = (HistoryClaim.worker_id == worker.id, HistoryClaim.archived_at.is_(None))
    total = await session.scalar(select(func.count()).select_from(HistoryClaim).where(*where)) or 0
    rows = (await session.scalars(select(HistoryClaim).where(*where).order_by(HistoryClaim.created_at.desc(), HistoryClaim.id).offset((page-1)*size).limit(size))).all()
    return ClaimPage(items=[await claim_view(session, row) for row in rows], total=total, page=page, size=size, pages=ceil(total/size))


async def request_view(session: AsyncSession, row: ConfirmationRequest, token: str | None = None) -> RequestView:
    """Return metadata and an optional once-only creation secret."""
    response = await session.scalar(select(CustomerResponse).where(CustomerResponse.request_id == row.id))
    return RequestView(id=row.id, claim_id=row.claim_id, operation_id=row.operation_id, revision=row.revision, expires_at=row.expires_at, revoked_at=row.revoked_at, token=token, response=receipt(response) if response else None)


async def issue_request(session: AsyncSession, user: User, claim_id: UUID, payload: RequestCreate, operation: UUID) -> RequestView:
    """Bind an immutable revision to its intended recipient; never recover secrets."""
    claim = await owned_claim(session, user, claim_id, lock=True)
    fingerprint = digest(payload.model_dump_json())
    previous = await session.scalar(select(ConfirmationRequest).where(ConfirmationRequest.claim_id == claim.id, ConfirmationRequest.operation_id == operation))
    if previous:
        if previous.payload_hash != fingerprint:
            raise FeatureError(409, "IDEMPOTENCY_CONFLICT", "This operation was used with another recipient.")
        return await request_view(session, previous)
    if claim.archived_at or claim.revision != payload.revision:
        raise FeatureError(409, "CLAIM_REVISION_CHANGED", "Reload the current claim.")
    if not claim.job_id and not payload.recipient_phone:
        raise FeatureError(422, "CONTACT_REQUIRED", "Provide the intended customer's international phone number.")
    if payload.recipient_phone and payload.recipient_phone == user.phone:
        raise FeatureError(403, "SELF_ATTESTATION", "You cannot request confirmation from your own contact.")
    active = await session.scalar(select(ConfirmationRequest.id).where(ConfirmationRequest.claim_id == claim.id, ConfirmationRequest.revision == claim.revision, ConfirmationRequest.revoked_at.is_(None), ConfirmationRequest.expires_at > now()))
    answered = await session.scalar(select(CustomerResponse.id).join(ConfirmationRequest).where(ConfirmationRequest.claim_id == claim.id, ConfirmationRequest.revision == claim.revision).limit(1))
    if answered:
        raise FeatureError(409, "RESPONSE_EXISTS", "This claim revision already received a response. Edit the claim before requesting another.")
    if active:
        raise FeatureError(409, "REQUEST_EXISTS", "Revoke the existing request before replacing it.")
    daily = await session.scalar(select(func.count()).select_from(ConfirmationRequest).join(HistoryClaim).where(HistoryClaim.worker_id == claim.worker_id, ConfirmationRequest.created_at > now()-timedelta(days=1))) or 0
    if daily >= 10:
        raise FeatureError(429, "REQUEST_DAILY_LIMIT", "Daily confirmation-request limit reached.", 3600)
    token = secrets.token_urlsafe(32)
    job = await session.get(Job, claim.job_id) if claim.job_id else None
    if claim.job_id and (job is None or job.client_id is None or job.worker_id != claim.worker_id):
        raise FeatureError(409, "CUSTOMER_UNATTRIBUTED", "The hiring customer must be attributed before issuing this request.")
    row = ConfirmationRequest(claim_id=claim.id, operation_id=operation, payload_hash=fingerprint, revision=claim.revision, snapshot=dict(claim.details), recipient_phone=payload.recipient_phone if not claim.job_id else None, hiring_customer_id=job.client_id if job else None, token_hash=digest(token), expires_at=now()+timedelta(days=7))
    session.add(row)
    await session.flush()
    audit(session, user.id, "history_request", row.id, "issued")
    return await request_view(session, row, token)


async def request_list(session: AsyncSession, user: User, claim_id: UUID, page: int, size: int) -> RequestPage:
    """List owned request metadata without contacts or secrets."""
    await owned_claim(session, user, claim_id)
    total = await session.scalar(select(func.count()).select_from(ConfirmationRequest).where(ConfirmationRequest.claim_id == claim_id)) or 0
    rows = (await session.scalars(select(ConfirmationRequest).where(ConfirmationRequest.claim_id == claim_id).order_by(ConfirmationRequest.created_at.desc(), ConfirmationRequest.id).offset((page-1)*size).limit(size))).all()
    return RequestPage(items=[await request_view(session, row) for row in rows], total=total, page=page, size=size, pages=ceil(total/size))


async def owned_request(session: AsyncSession, user: User, request_id: UUID) -> ConfirmationRequest:
    """Resolve an owned request for explicit revocation."""
    row = await session.get(ConfirmationRequest, request_id)
    if row is None:
        raise FeatureError(404, "REQUEST_NOT_FOUND", "Confirmation request not found.")
    await owned_claim(session, user, row.claim_id, lock=True)
    return await session.scalar(select(ConfirmationRequest).where(ConfirmationRequest.id == row.id).with_for_update())


async def lookup_request(session: AsyncSession, token: str, *, lock: bool = False) -> tuple[ConfirmationRequest, HistoryClaim]:
    """Check expiry, archive and current revision on every capability access."""
    if not 32 <= len(token) <= 128:
        raise FeatureError(404, "LINK_NOT_FOUND", "Confirmation link not found.")
    query = select(ConfirmationRequest).where(ConfirmationRequest.token_hash == digest(token))
    # Claim first is the common lock order used by owner edits and responses.
    found = await session.scalar(query)
    if found is None:
        raise FeatureError(404, "LINK_NOT_FOUND", "Confirmation link not found.")
    cq = select(HistoryClaim).where(HistoryClaim.id == found.claim_id)
    claim = await session.scalar(cq.with_for_update().execution_options(populate_existing=True) if lock else cq)
    row = await session.scalar(query.with_for_update().execution_options(populate_existing=True)) if lock else found
    if row.revoked_at or aware(row.expires_at) <= now() or claim.archived_at or claim.revision != row.revision:
        raise FeatureError(410, "LINK_UNAVAILABLE", "This confirmation request has expired or been revoked.")
    return row, claim


async def authorize(session: AsyncSession, row: ConfirmationRequest, claim: HistoryClaim, user: User | None, guest: str | None) -> tuple[str, bool]:
    """Match the current hiring customer or a live scoped contact session."""
    if claim.job_id:
        job = await session.get(Job, claim.job_id, populate_existing=True)
        if job is None or job.worker_id != claim.worker_id or not user or not user.is_active or job.client_id is None or job.client_id != user.id or row.hiring_customer_id != user.id:
            raise FeatureError(403, "CUSTOMER_ACCOUNT_REQUIRED", "Sign in with the hiring customer's existing account.")
        return "matched_hiring_account", False
    if row.challenge_sandbox and get_settings().environment != "development":
        raise FeatureError(403, "CONTACT_VERIFICATION_REQUIRED", "Production requires real contact verification.")
    if not guest or not row.session_hash or not row.session_expires_at or aware(row.session_expires_at) <= now() or not hmac.compare_digest(row.session_hash, digest(guest)):
        raise FeatureError(403, "CONTACT_VERIFICATION_REQUIRED", "Verify the intended phone contact before continuing.")
    return "contact_verified", row.challenge_sandbox


async def start_challenge(session: AsyncSession, token: str) -> tuple[bool, str | None]:
    """Deliver a bounded challenge only to the stored recipient; never log the code."""
    row, claim = await lookup_request(session, token, lock=True)
    if claim.job_id:
        raise FeatureError(409, "ACCOUNT_REQUIRED", "This job requires the existing hiring-customer account.")
    if row.challenge_sent_at and aware(row.challenge_sent_at)+timedelta(seconds=60) > now():
        raise FeatureError(429, "CHALLENGE_RESEND_LIMIT", "Wait before requesting another code.", 60)
    if row.challenge_send_count >= 5:
        raise FeatureError(429, "CHALLENGE_SEND_LIMIT", "This request has reached its contact-code delivery limit.", 3600)
    provider = contact_provider()
    code = None
    if provider:
        challenge = await provider.send(row.recipient_phone)
        row.challenge_reference = challenge.reference
        row.challenge_sandbox = challenge.sandbox
        row.challenge_hash = None
    else:
        code = f"{secrets.randbelow(1000000):06d}"
        row.challenge_reference = "development"
        row.challenge_sandbox = True
        row.challenge_hash = digest(f"{row.id}:{code}")
    row.challenge_send_count += 1
    row.challenge_sent_at = now()
    row.challenge_expires_at = now()+timedelta(minutes=10)
    row.challenge_attempts = 0
    row.session_hash = None
    row.session_expires_at = None
    return row.challenge_sandbox, code


async def check_challenge(session: AsyncSession, token: str, code: str) -> str:
    """Consume the challenge and return one short-lived request-scoped secret."""
    row, claim = await lookup_request(session, token, lock=True)
    if claim.job_id or row.challenge_expires_at is None or aware(row.challenge_expires_at) <= now() or row.challenge_attempts >= 5:
        raise FeatureError(400, "CHALLENGE_UNAVAILABLE", "Request a new code.")
    row.challenge_attempts += 1
    if row.challenge_sandbox:
        # Recheck environment; a persisted sandbox challenge never works in production.
        provider = contact_provider()
        valid = provider is None and row.challenge_hash is not None and hmac.compare_digest(row.challenge_hash, digest(f"{row.id}:{code}"))
    else:
        provider = contact_provider()
        valid = provider is not None and await provider.check(row.recipient_phone, code, row.challenge_reference)
    if not valid:
        raise FeatureError(400, "CODE_INVALID", "The verification code is incorrect.")
    secret = secrets.token_urlsafe(32)
    row.session_hash = digest(secret)
    row.session_expires_at = min(aware(row.expires_at), now()+timedelta(minutes=30))
    row.challenge_expires_at = now()
    row.challenge_hash = None
    audit(session, None, "history_request", row.id, "contact_checked", {"sandbox": row.challenge_sandbox})
    return secret


async def submit_response(session: AsyncSession, token: str, user: User | None, guest: str | None, payload: CustomerDecision, operation: UUID, ip: str, agent: str) -> ResponseReceipt:
    """Atomically persist an explicit decision and attribution, never a scored outcome."""
    row, claim = await lookup_request(session, token, lock=True)
    method, sandbox = await authorize(session, row, claim, user, guest)
    fingerprint = digest(payload.model_dump_json())
    previous = await session.scalar(select(CustomerResponse).where(CustomerResponse.request_id == row.id))
    if previous:
        if previous.operation_id == operation and previous.payload_hash == fingerprint:
            return receipt(previous)
        raise FeatureError(409, "RESPONSE_EXISTS", "A response has already been recorded for this request.")
    if payload.decision == "confirmed" and not payload.declares_customer:
        raise FeatureError(422, "CUSTOMER_DECLARATION_REQUIRED", "Confirm that you were the customer for this job.")
    if method == "contact_verified" and payload.declares_customer:
        method = "contact_verified_relationship_declared"
    response = CustomerResponse(declares_customer=payload.declares_customer, request_id=row.id, actor_id=user.id if claim.job_id else None, operation_id=operation, payload_hash=fingerprint, decision=payload.decision, attribution=method, sandbox=sandbox)
    session.add(response)
    await session.flush()
    audit(session, response.actor_id, "history_response", response.id, "submitted", {"attribution": method, "sandbox": sandbox, "consent_version": "history-v1", "declares_customer": payload.declares_customer, "ip_hash": digest(ip), "user_agent_hash": digest(agent)})
    return receipt(response)


async def history_counts(session: AsyncSession, worker_id: UUID) -> InformalHistoryCounts:
    """Whitelist aggregate evidence; no declarations enter either assessment path."""
    declared = await session.scalar(select(func.count()).select_from(HistoryClaim).where(HistoryClaim.worker_id == worker_id, HistoryClaim.job_id.is_(None), HistoryClaim.archived_at.is_(None))) or 0
    # A stale account/job mapping cannot count as current customer corroboration.
    counts = (await session.execute(select(CustomerResponse.attribution, CustomerResponse.sandbox).join(ConfirmationRequest).join(HistoryClaim).outerjoin(Job, HistoryClaim.job_id == Job.id).where(or_(HistoryClaim.job_id.is_(None), (Job.client_id == CustomerResponse.actor_id) & (ConfirmationRequest.hiring_customer_id == CustomerResponse.actor_id)), HistoryClaim.worker_id == worker_id, HistoryClaim.archived_at.is_(None), HistoryClaim.revision == ConfirmationRequest.revision, CustomerResponse.decision == "confirmed", CustomerResponse.withdrawn_at.is_(None)))).all()
    return InformalHistoryCounts(declared_jobs=declared, contact_attested_jobs=sum(m == "contact_verified_relationship_declared" and not s for m, s in counts), sandbox_attested_jobs=sum(s for _, s in counts), matched_customer_jobs=sum(m == "matched_hiring_account" for m, _ in counts))
