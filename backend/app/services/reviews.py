"""Protected-job review eligibility and transactional abuse prevention."""
from datetime import timedelta
from uuid import UUID
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis
from redis.exceptions import RedisError
from app.core.config import get_settings
from app.models.domain import Dispute, DisputeStatus, EscrowStatus, EscrowTransaction, IdentityVerification, InsurancePolicy, InsuranceStatus, Job, JobConfirmation, JobStatus, JobType, NormalizedOutcome, OutcomeStatus, ProviderOperation, ProviderOperationStatus, User, Worker
from app.models.portability import Review
from app.schemas.portability import ReviewEligibility, ReviewRequest, ReviewResponse
from app.schemas.portability import CustomerJobPage
from app.services.feature_common import FeatureError, audit, aware, digest, now
from app.services.trust_scoring.assessment import assess_worker


async def limit_attempts(user_id: str, ip: str) -> None:
    """Atomically enforce fixed-minute limits across app processes; fail closed."""
    cfg = get_settings()
    bucket = int(now().timestamp()) // 60
    keys = [f"reviews:user:{user_id}:{bucket}", f"reviews:ip:{digest(ip)}:{bucket}"]
    script = """
    local results = {}
    for i,key in ipairs(KEYS) do
      local n = redis.call('INCR', key)
      if n == 1 then redis.call('EXPIRE', key, 60) end
      results[i] = n
    end
    return results
    """
    try:
        async with Redis.from_url(cfg.redis_url, socket_connect_timeout=2, socket_timeout=2) as redis:
            counts = await redis.eval(script, 2, *keys)
    except (RedisError, OSError) as error:
        raise FeatureError(503, "LIMITER_UNAVAILABLE", "Review submission is temporarily unavailable. Your draft has not been submitted.", 60) from error
    if counts[0] > cfg.review_user_attempts_per_minute or counts[1] > cfg.review_ip_attempts_per_minute:
        raise FeatureError(429, "REVIEW_RATE_LIMIT", "Too many review attempts. Wait before retrying.", 60-int(now().timestamp()) % 60)


def review_response(review: Review) -> ReviewResponse:
    """Expose receipt facts without private review comments or identity references."""
    return ReviewResponse(id=review.id, job_id=review.job_id, rating=review.rating, submitted_at=review.created_at)


async def eligibility(session: AsyncSession, user: User, job_id: UUID) -> tuple[ReviewEligibility, IdentityVerification | None, NormalizedOutcome | None]:
    """Check authoritative ownership, identity, confirmation, protection and dispute records."""
    job = await session.get(Job, job_id)
    if job is None or job.client_id != user.id or not user.is_active:
        raise FeatureError(404, "JOB_NOT_FOUND", "No hiring-customer job is available for this account.")
    reasons = []
    review = await session.scalar(select(Review).where(Review.job_id == job.id))
    if review:
        reasons.append("This job already has a review.")
    if job.job_type != JobType.INDEPENDENT:
        reasons.append("Only protected independent jobs can be reviewed here.")
    if job.status not in (JobStatus.COMPLETED, JobStatus.RELEASED):
        reasons.append("This job has not reached completed status.")
    identity = await session.scalar(select(IdentityVerification).where(IdentityVerification.user_id == user.id,
        IdentityVerification.check_type == "identity").order_by(IdentityVerification.created_at.desc(), IdentityVerification.id.desc()).limit(1))
    sandbox = identity is not None and identity.provider == "stub"
    if identity is None or identity.status != "verified" or (sandbox and get_settings().environment != "development"):
        reasons.append("A successful hiring-customer identity check is required.")
    worker = await session.get(Worker, job.worker_id)
    confirmations = list((await session.scalars(select(JobConfirmation).where(JobConfirmation.job_id == job.id,
        JobConfirmation.confirmed.is_(True)))).all())
    client_confirmed = any(c.confirmer_role == "client" and c.confirmer_id == user.id and aware(c.confirmed_at) <= now() for c in confirmations)
    worker_confirmed = worker is not None and any(c.confirmer_role == "worker" and c.confirmer_id == worker.user_id and aware(c.confirmed_at) <= now() for c in confirmations)
    if not client_confirmed or not worker_confirmed:
        reasons.append("The hiring customer and worker must explicitly confirm completion. Auto-release alone is insufficient.")
    outcome = await session.scalar(select(NormalizedOutcome).where(NormalizedOutcome.job_id == job.id,
        NormalizedOutcome.worker_id == job.worker_id, NormalizedOutcome.verified.is_(True),
        NormalizedOutcome.completion_confirmed.is_(True), NormalizedOutcome.status == OutcomeStatus.COMPLETED)
        .order_by(NormalizedOutcome.occurred_at.desc(), NormalizedOutcome.id).limit(1))
    if outcome is None:
        reasons.append("A verified, completion-confirmed work outcome is required.")
    if await session.scalar(select(Dispute.id).where(Dispute.job_id == job.id, Dispute.status.in_([DisputeStatus.OPEN, DisputeStatus.UNDER_REVIEW])).limit(1)):
        reasons.append("This job has an open dispute.")
    escrows = list((await session.scalars(select(EscrowTransaction).where(EscrowTransaction.job_id == job.id))).all())
    insurance = await session.scalar(select(InsurancePolicy).where(InsurancePolicy.job_id == job.id))
    premium_confirmed = await session.scalar(select(ProviderOperation.id).where(ProviderOperation.entity_type == "job",
        ProviderOperation.entity_id == job.id, ProviderOperation.operation_type == "premium_payment",
        ProviderOperation.status == ProviderOperationStatus.SUCCEEDED).limit(1))
    protected = insurance is not None and insurance.premium > 0 and insurance.provider_reference and insurance.status in (InsuranceStatus.ACTIVE, InsuranceStatus.EXPIRED) and premium_confirmed
    protected = protected and any(e.status in (EscrowStatus.HELD, EscrowStatus.RELEASED) and e.provider_reference and e.cover_active
        and e.amount >= job.agreed_amount and e.micro_premium == insurance.premium for e in escrows)
    if any(e.status in (EscrowStatus.FAILED, EscrowStatus.REFUNDED) for e in escrows):
        protected = False
    if not protected:
        reasons.append("Stored funded escrow, paid premium, and activated cover evidence are required.")
    return ReviewEligibility(job_id=job.id, job_title=job.title, eligible=not reasons, reasons=reasons,
        sandbox_identity=sandbox, existing_review=review_response(review) if review else None), identity, outcome


async def submit_review(session: AsyncSession, user: User, job_id: UUID, payload: ReviewRequest, key: str) -> ReviewResponse:
    """Serialize per reviewer/job, then commit review, rating and audit as one unit."""
    await session.execute(select(User.id).where(User.id == user.id).with_for_update())
    await session.execute(select(Job.id).where(Job.id == job_id).with_for_update())
    result, identity, outcome = await eligibility(session, user, job_id)
    previous = await session.scalar(select(Review).where(Review.job_id == job_id))
    payload_hash = digest(payload.model_dump_json())
    if previous:
        if previous.reviewer_id == user.id and previous.idempotency_key == key and previous.payload_hash == payload_hash:
            return review_response(previous)
        raise FeatureError(409, "REVIEW_EXISTS", "This job already has a review.")
    if not result.eligible:
        raise FeatureError(403, "REVIEW_INELIGIBLE", " ".join(result.reasons))
    count = await session.scalar(select(func.count()).select_from(Review).where(Review.reviewer_id == user.id, Review.created_at > now()-timedelta(hours=24)))
    if count >= get_settings().review_daily_limit:
        oldest = await session.scalar(select(func.min(Review.created_at)).where(Review.reviewer_id == user.id, Review.created_at > now()-timedelta(hours=24)))
        seconds = max(1, int((aware(oldest)+timedelta(hours=24)-now()).total_seconds())+1)
        raise FeatureError(429, "REVIEW_VELOCITY_LIMIT", "Daily review limit reached. Wait before reviewing another job.", seconds)
    row = Review(job_id=job_id, reviewer_id=user.id, identity_verification_id=identity.id,
        rating=payload.rating, comment=payload.comment, idempotency_key=key, payload_hash=payload_hash)
    session.add(row)
    outcome.rating = payload.rating
    await session.flush()
    audit(session, user.id, "review", row.id, "submitted", {"job_id": str(job_id), "sandbox_identity": result.sandbox_identity})
    await assess_worker(session, outcome.worker_id, "generic")
    return review_response(row)


async def customer_jobs(session: AsyncSession, user: User, page: int, size: int) -> "CustomerJobPage":
    """Paginate jobs attributed to the current hiring customer only."""
    from math import ceil
    from app.schemas.portability import CustomerJob, CustomerJobPage
    total = await session.scalar(select(func.count()).select_from(Job).where(Job.client_id == user.id))
    rows = (await session.scalars(select(Job).where(Job.client_id == user.id).order_by(Job.created_at.desc(), Job.id).offset((page-1)*size).limit(size))).all()
    return CustomerJobPage(items=[CustomerJob(id=job.id, title=job.title, status=job.status.value, created_at=job.created_at) for job in rows], total=total, page=page, size=size, pages=ceil(total/size))
