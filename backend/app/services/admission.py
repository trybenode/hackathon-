"""Policy-scoped onboarding permissions, separate from immutable verified trust assessments."""

from datetime import timedelta
from decimal import Decimal
import json
from math import ceil
from uuid import UUID
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import get_settings
from app.models.admission import (
    OnboardingCase,
    OnboardingPolicy,
    OwnershipImport,
    ReviewDecision,
)
from app.models.domain import Job, JobStatus, User, Worker
from app.models.portability import PlatformKey
from app.services.trust_scoring.assessment import WorkerAssessment
from app.schemas.admission import (
    CaseCreate,
    DecisionInput,
    OnboardingView,
    PolicySettings,
    PolicyUpdate,
    Restrictions,
)
from app.services.feature_common import FeatureError, now, aware, digest, audit
from app.services.review_access import reviewer, worker_for, consent

FIRST_PARTY = "first_party"
ENVIRONMENT = "production"
ACTIVE = (
    JobStatus.DRAFT,
    JobStatus.ACCEPTED,
    JobStatus.IN_PROGRESS,
    JobStatus.SUBMITTED,
    JobStatus.COMPLETED,
    JobStatus.DISPUTED,
)


def enabled() -> None:
    """Gate rollout independently of unsigned document imports."""
    if not get_settings().additional_verification_enabled:
        raise FeatureError(
            404, "ONBOARDING_DISABLED", "Additional verification is not enabled."
        )


async def policy(
    session: AsyncSession, scope: str, environment: str, platform_type: str
) -> tuple[PolicySettings, int]:
    """First-party defaults are fixed; external platforms explicitly opt into the new actions."""
    if scope == FIRST_PARTY:
        return PolicySettings(enabled=True, allow_approved=False), 1
    row = await session.scalar(
        select(OnboardingPolicy).where(
            OnboardingPolicy.scope == scope,
            OnboardingPolicy.environment == environment,
            OnboardingPolicy.platform_type == platform_type,
        )
    )
    return (
        (PolicySettings.model_validate(row.settings), row.version)
        if row
        else (PolicySettings(), 1)
    )


async def save_policy(
    session: AsyncSession,
    actor: User,
    scope: str,
    environment: str,
    platform_type: str,
    payload: PolicyUpdate,
) -> dict:
    """Reviewers version tenant policy updates; a stale policy cannot silently overwrite one."""
    enabled()
    if scope == FIRST_PARTY:
        raise FeatureError(
            403, "FIXED_POLICY", "First-party limits are fixed by the pilot policy."
        )
    await reviewer(session, actor, scope, environment)
    return await _write_policy(
        session, scope, environment, platform_type, payload, actor.id
    )


async def save_platform_policy(
    session: AsyncSession,
    principal: PlatformKey,
    platform_type: str,
    payload: PolicyUpdate,
) -> dict:
    """An authenticated scoring-scoped platform key can configure only its own policy."""
    enabled()
    return await _write_policy(
        session,
        str(principal.organization_id),
        principal.environment,
        platform_type,
        payload,
        None,
        principal.id,
    )


async def _write_policy(
    session: AsyncSession,
    scope: str,
    environment: str,
    platform_type: str,
    payload: PolicyUpdate,
    actor_id: UUID | None,
    key_id: UUID | None = None,
) -> dict:
    # Serialize a missing-policy insert with other reviewer policy writes for this organization.
    from app.models.domain import Organization

    org = await session.scalar(
        select(Organization).where(Organization.id == UUID(scope)).with_for_update()
    )
    if not org:
        raise FeatureError(404, "PLATFORM_NOT_FOUND", "Platform not found.")
    row = await session.scalar(
        select(OnboardingPolicy)
        .where(
            OnboardingPolicy.scope == scope,
            OnboardingPolicy.environment == environment,
            OnboardingPolicy.platform_type == platform_type,
        )
        .with_for_update()
    )
    current = row.version if row else 1
    if current != payload.version:
        raise FeatureError(409, "STALE_POLICY", "Reload the current onboarding policy.")
    settings = payload.settings.model_dump(mode="json")
    if row:
        row.settings = settings
        row.version += 1
    else:
        row = OnboardingPolicy(
            scope=scope,
            environment=environment,
            platform_type=platform_type,
            version=2,
            settings=settings,
        )
        session.add(row)
    await session.flush()
    audit(
        session,
        actor_id,
        "onboarding_policy",
        row.id,
        "updated",
        {"version": row.version, "key_id": str(key_id) if key_id else None},
    )
    return {"version": row.version, "settings": row.settings}


async def assessment_for(
    session: AsyncSession,
    worker_id: UUID,
    scope: str,
    environment: str,
    platform_type: str,
) -> WorkerAssessment:
    """Reuse the verified scorer and existing tenant scoring configuration unchanged."""
    from app.services.trust_scoring.assessment import assess_worker

    config, name = None, None
    if scope != FIRST_PARTY:
        from app.models.developer import ScoringConfig
        from app.services.scoring_config import _to_config, policy_name

        row = await session.scalar(
            select(ScoringConfig).where(
                ScoringConfig.organization_id == UUID(scope),
                ScoringConfig.environment == environment,
                ScoringConfig.platform_type == platform_type,
            )
        )
        if row:
            config, name = _to_config(row), policy_name(
                UUID(scope), environment, platform_type
            )
    return await assess_worker(
        session, worker_id, platform_type, config=config, policy_name=name
    )


async def evaluate(
    session: AsyncSession,
    worker_id: UUID,
    scope: str = FIRST_PARTY,
    environment: str = ENVIRONMENT,
    platform_type: str = "generic",
    assessment: WorkerAssessment | None = None,
) -> OnboardingView | None:
    """Derive the next action from current checks, policy and evidence, never mutate trust scores."""
    if not get_settings().additional_verification_enabled:
        return None
    settings, policy_version = await policy(session, scope, environment, platform_type)
    if not settings.enabled:
        return None
    await consent(session, worker_id, scope, environment)
    worker = await session.get(Worker, worker_id)
    if not worker:
        raise FeatureError(404, "WORKER_NOT_FOUND", "Worker not found.")
    from app.services.worker_verification import verification_for
    from app.services.worker_record import latest_check

    checks = await verification_for(session, worker)
    identities = [
        await latest_check(session, worker.user_id, kind)
        for kind in ("identity", "liveness")
    ]
    imports = (
        await session.execute(
            select(OwnershipImport.id, OwnershipImport.state, OwnershipImport.version)
            .where(
                OwnershipImport.worker_id == worker_id,
                OwnershipImport.state != "preparing",
            )
            .order_by(OwnershipImport.id)
        )
    ).all()
    canonical_assessment = await assessment_for(
        session, worker_id, scope, environment, platform_type
    )
    assessment = assessment or canonical_assessment
    evidence = digest(
        json.dumps(
            {
                "assessment": str(canonical_assessment.id),
                "checks": [str(c.id) if c else None for c in identities],
                "check_status": [checks.identity, checks.liveness],
                "guarantor": checks.guarantor,
                "guarantor_until": str(checks.guarantor_valid_until),
                "imports": [tuple(str(v) for v in item) for item in imports],
            },
            sort_keys=True,
        )
    )
    row = await session.scalar(
        select(OnboardingCase).where(
            OnboardingCase.worker_id == worker_id,
            OnboardingCase.scope == scope,
            OnboardingCase.environment == environment,
            OnboardingCase.platform_type == platform_type,
        )
    )
    base = dict(
        policy_version=policy_version,
        evidence_revision=evidence,
        case_id=row.id if row else None,
        case_version=row.version if row else None,
        review_message=row.last_reason if row else None,
    )
    if assessment.band != "Building History" and not assessment.decision:
        return OnboardingView(
            action="declined", reason_codes=["SCORING_RESTRICTION"], **base
        )
    missing = [
        key
        for key, value in (("identity", checks.identity), ("liveness", checks.liveness))
        if value != "verified"
    ]
    if missing:
        return OnboardingView(
            action="additional_verification",
            requirements=missing,
            reason_codes=["GENUINE_CHECKS_REQUIRED"],
            next_steps=["complete_verification"],
            **base
        )
    if assessment.band != "Building History" and assessment.decision:
        return OnboardingView(
            action="approved", reason_codes=["VERIFIED_SCORING_POLICY"], **base
        )
    if (
        row
        and row.evidence_revision == evidence
        and row.policy_version == policy_version
    ):
        if row.state == "pending":
            return OnboardingView(
                action="manual_review", reason_codes=["REVIEW_PENDING"], **base
            )
        if row.state == "declined":
            return OnboardingView(
                action="declined",
                reason_codes=["REVIEW_DECLINED"],
                next_steps=["request_reconsideration"],
                **base
            )
        if (
            row.state in {"approved", "limited"}
            and row.expires_at
            and aware(row.expires_at) > now()
        ):
            if row.state == "approved" and not settings.allow_approved:
                pass
            elif row.state == "limited" and not settings.allow_limited:
                pass
            else:
                return OnboardingView(
                    action=row.state,
                    restrictions=(
                        Restrictions.model_validate(row.restrictions)
                        if row.restrictions
                        else None
                    ),
                    expires_at=row.expires_at,
                    reason_codes=["REVIEW_APPROVED"],
                    **base
                )
        if row.state == "changes_requested":
            return OnboardingView(
                action="manual_review",
                requirements=["supporting_information"],
                reason_codes=["INFORMATION_REQUESTED"],
                next_steps=["submit_review"],
                **base
            )
    return OnboardingView(
        action="manual_review",
        reason_codes=["INSUFFICIENT_VERIFIED_HISTORY"],
        next_steps=["submit_review"],
        **base
    )


async def submit_case(
    session: AsyncSession, user: User, payload: CaseCreate
) -> OnboardingView:
    """Create/resubmit one case per worker and policy context after required checks pass."""
    enabled()
    worker = await worker_for(session, user, lock=True)
    scope = str(payload.organization_id) if payload.organization_id else FIRST_PARTY
    current = await evaluate(
        session, worker.id, scope, ENVIRONMENT, payload.platform_type
    )
    if current is None:
        raise FeatureError(
            409,
            "POLICY_DISABLED",
            "This platform has not enabled additional-verification onboarding.",
        )
    if current.action == "additional_verification":
        raise FeatureError(
            409,
            "VERIFICATION_REQUIRED",
            "Complete genuine identity and liveness checks first.",
        )
    if current.action in {"approved", "limited"}:
        return current
    if current.reason_codes == ["SCORING_RESTRICTION"]:
        raise FeatureError(
            409, "SCORING_RESTRICTION", "A reviewer cannot override disqualification."
        )
    row = await session.scalar(
        select(OnboardingCase)
        .where(
            OnboardingCase.worker_id == worker.id,
            OnboardingCase.scope == scope,
            OnboardingCase.environment == ENVIRONMENT,
            OnboardingCase.platform_type == payload.platform_type,
        )
        .with_for_update()
    )
    if row:
        if (
            row.state == "pending"
            and row.evidence_revision == current.evidence_revision
            and row.policy_version == current.policy_version
        ):
            return current
        if (
            row.state == "declined"
            and row.evidence_revision == current.evidence_revision
        ):
            raise FeatureError(
                409,
                "NEW_EVIDENCE_REQUIRED",
                "Provide corrected or additional evidence before reconsideration.",
            )
        if row.state == "changes_requested" and not payload.response:
            raise FeatureError(
                422,
                "RESPONSE_REQUIRED",
                "Respond to the reviewer's request before resubmitting.",
            )
        row.version += 1
        row.state = "pending"
        row.evidence_revision = current.evidence_revision
        row.policy_version = current.policy_version
        row.expires_at = None
        row.restrictions = None
    else:
        row = OnboardingCase(
            worker_id=worker.id,
            scope=scope,
            environment=ENVIRONMENT,
            platform_type=payload.platform_type,
            policy_version=current.policy_version,
            evidence_revision=current.evidence_revision,
        )
        session.add(row)
    row.worker_response = payload.response
    await session.flush()
    audit(
        session,
        user.id,
        "onboarding_case",
        row.id,
        "submitted",
        {"version": row.version, "worker_response": payload.response},
    )
    return await evaluate(session, worker.id, scope, ENVIRONMENT, payload.platform_type)


async def decide(
    session: AsyncSession, actor: User, case_id: UUID, payload: DecisionInput
) -> OnboardingView:
    """Review an evidence snapshot under its tenant policy without overriding verified scoring."""
    enabled()
    initial = await session.get(OnboardingCase, case_id)
    if not initial:
        raise FeatureError(404, "CASE_NOT_FOUND", "Onboarding case not found.")
    await reviewer(
        session,
        actor,
        "operations" if initial.scope == FIRST_PARTY else initial.scope,
        initial.environment,
    )
    worker = await session.scalar(
        select(Worker).where(Worker.id == initial.worker_id).with_for_update()
    )
    row = await session.get(
        OnboardingCase, case_id, with_for_update=True, populate_existing=True
    )
    if worker.user_id == actor.id:
        raise FeatureError(403, "SELF_REVIEW", "You cannot decide your own onboarding.")
    if row.version != payload.version:
        raise FeatureError(409, "STALE_REVISION", "Reload the case before deciding.")
    current = await evaluate(
        session, worker.id, row.scope, row.environment, row.platform_type
    )
    if (
        current is None
        or current.evidence_revision != row.evidence_revision
        or current.policy_version != row.policy_version
    ):
        raise FeatureError(
            409,
            "STALE_EVIDENCE",
            "Policy or evidence changed; worker must resubmit this case.",
        )
    settings, _ = await policy(session, row.scope, row.environment, row.platform_type)
    if payload.decision != "revoke":
        if row.state != "pending":
            raise FeatureError(
                409, "REVIEW_STATE", "Only a pending case can be decided."
            )
        if current.action != "manual_review":
            raise FeatureError(
                409,
                "VERIFICATION_REQUIRED",
                "Current verification and scoring eligibility must hold.",
            )
    if payload.decision == "approve":
        if not settings.allow_approved or row.scope == FIRST_PARTY:
            raise FeatureError(
                409, "LIMITED_ONLY", "This policy allows limited approval only."
            )
        row.state = "approved"
    elif payload.decision == "approve_limited":
        if not settings.allow_limited:
            raise FeatureError(
                409,
                "LIMITED_DISABLED",
                "Limited onboarding is disabled by this policy.",
            )
        row.state = "limited"
        row.restrictions = settings.restrictions.model_dump(mode="json")
    elif payload.decision == "decline":
        row.state = "declined"
    elif payload.decision == "request_information":
        row.state = "changes_requested"
    elif payload.decision == "revoke":
        row.state = "revoked"
    row.last_reason = payload.reason
    row.version += 1
    row.expires_at = (
        now() + timedelta(days=settings.approval_days)
        if row.state in {"approved", "limited"}
        else None
    )
    session.add(
        ReviewDecision(
            actor_id=actor.id,
            entity_type="onboarding_case",
            entity_id=row.id,
            version=row.version,
            decision=payload.decision,
            reason=payload.reason,
            evidence_revision=row.evidence_revision,
            policy_version=row.policy_version,
        )
    )
    audit(
        session,
        actor.id,
        "onboarding_case",
        row.id,
        "reviewed",
        {"decision": payload.decision, "version": row.version},
    )
    await session.flush()
    return await evaluate(
        session, worker.id, row.scope, row.environment, row.platform_type
    )


async def queue(
    session: AsyncSession,
    actor: User,
    scope: str,
    environment: str,
    page: int,
    size: int,
) -> dict:
    """Paginate private review cases; tenant documents and other organizations never leak."""
    enabled()
    await reviewer(
        session, actor, "operations" if scope == FIRST_PARTY else scope, environment
    )
    query = select(OnboardingCase).where(
        OnboardingCase.scope == scope, OnboardingCase.environment == environment
    )
    if scope != FIRST_PARTY:
        from sqlalchemy import cast, String
        from app.models.portability import PlatformGrant, WorkerLink

        grants = (
            select(WorkerLink.worker_id)
            .join(PlatformGrant, PlatformGrant.id == WorkerLink.grant_id)
            .where(
                WorkerLink.organization_id == UUID(scope),
                PlatformGrant.revoked_at.is_(None),
                PlatformGrant.expires_at > now(),
                cast(PlatformGrant.permissions, String).like('%"read_history"%'),
            )
        )
        query = query.where(OnboardingCase.worker_id.in_(grants))
    total = await session.scalar(select(func.count()).select_from(query.subquery()))
    rows = (
        await session.scalars(
            query.order_by(OnboardingCase.created_at.desc(), OnboardingCase.id)
            .offset((page - 1) * size)
            .limit(size)
        )
    ).all()
    items = []
    from app.services.ownership_imports import provisional

    for row in rows:
        worker = await session.get(Worker, row.worker_id)
        person = await session.get(User, worker.user_id)
        current = await evaluate(
            session, row.worker_id, row.scope, row.environment, row.platform_type
        )
        from app.services.worker_verification import verification_for

        checks = await verification_for(session, worker)
        assessment = await assessment_for(
            session, worker.id, row.scope, row.environment, row.platform_type
        )
        items.append(
            {
                "worker_response": row.worker_response,
                "assessment": {
                    "band": assessment.band,
                    "decision": assessment.decision,
                    "confidence": float(assessment.confidence),
                    "score": (
                        float(assessment.score)
                        if assessment.score is not None
                        else None
                    ),
                    "explanation_summary": assessment.explanation_summary,
                    "signals_used": assessment.signals_used,
                },
                "verification": {
                    "identity": checks.identity,
                    "liveness": checks.liveness,
                    "guarantor": checks.guarantor,
                },
                "id": row.id,
                "worker_id": worker.id,
                "display_name": person.display_name,
                "version": row.version,
                "state": row.state,
                "platform_type": row.platform_type,
                "last_reason": row.last_reason,
                "onboarding": current.model_dump(mode="json") if current else None,
                "provisional": (await provisional(session, worker.id)).model_dump(
                    mode="json"
                ),
            }
        )
    return {
        "items": items,
        "total": total,
        "page": page,
        "size": size,
        "pages": ceil(total / size),
    }


async def enforce_job(
    session: AsyncSession,
    worker_id: UUID,
    amount: Decimal,
    *,
    exclude_job_id: UUID | None = None
) -> None:
    """Serialize first-party limits; existing funded jobs never call this settlement gate."""
    if not get_settings().additional_verification_enabled:
        return
    await session.scalar(select(Worker).where(Worker.id == worker_id).with_for_update())
    current = await evaluate(session, worker_id)
    if current is None:
        return
    if current.action not in {"approved", "limited"}:
        raise FeatureError(
            403,
            "ONBOARDING_REQUIRED",
            "Complete additional verification and onboarding review before starting another job.",
        )
    if current.action == "limited":
        if amount > current.restrictions.max_job_value:
            raise FeatureError(
                403,
                "JOB_VALUE_LIMIT",
                "Limited onboarding allows jobs up to NGN25,000.",
            )
        query = (
            select(func.count())
            .select_from(Job)
            .where(Job.worker_id == worker_id, Job.status.in_(ACTIVE))
        )
        if exclude_job_id:
            query = query.where(Job.id != exclude_job_id)
        if await session.scalar(query) >= current.restrictions.max_active_jobs:
            raise FeatureError(
                409,
                "ACTIVE_JOB_LIMIT",
                "Finish or cancel the active job before creating another.",
            )
