"""Purpose: Score a worker from persisted verified outcomes and reuse unchanged assessments.

Dependencies: SQLAlchemy, app.models.domain, and the pure scoring/signal modules.
Used by: the trust query endpoint and outcome-ingestion service.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.domain import (
    AssessmentStatus,
    NormalizedOutcome,
    TrustAssessment,
    TrustPolicy,
    Worker,
)
from app.services.normalisation import normalise_db_row
from app.services.trust_scoring.scoring import PRESETS, PlatformConfig, score_worker
from app.services.trust_scoring.signals import aggregate

SCORING_VERSION = "1"

# blank template that defines exactly what information will be handed back at the end
@dataclass(frozen=True)
class WorkerAssessment:
    id: UUID
    worker_id: UUID
    decision: bool
    confidence: Decimal
    #supposed to enums I think for band and status
    band: str 
    status: str
    signals_used: list[str]
    explanation_summary: str
    platform_type_applied: str


class UnknownWorkerError(ValueError):
    """Raised when an assessment is requested for an unknown worker."""

# takes a messy job record and neatly copies only the important details
def _canonical_outcome(outcome: NormalizedOutcome) -> dict[str, Any]:
    return {
        "id": str(outcome.id),
        "status": outcome.status.value,
        "cancelled_by": outcome.cancelled_by,
        "dispute_resolution": outcome.dispute_resolution,
        "client_id": outcome.client_id,
        "rating": str(outcome.rating) if outcome.rating is not None else None,
        "flags": outcome.quality_flags or [],
        "normalization_version": outcome.normalization_version,
        "import_method": outcome.import_method,
        "source_platform": outcome.source_platform,
        "occurred_at": outcome.occurred_at.isoformat(),
    }

# takes all of the worker's past jobs, the specific grading rules being used, and squishes them together into a unique, scrambled code
"""
If a worker has 5 jobs, it makes a specific fingerprint.
If they do a 6th job, the fingerprint changes.
"""
def _fingerprint(
    outcomes: list[NormalizedOutcome], platform_type: str, config: PlatformConfig
) -> str:
    payload = {
        "platform_type": platform_type,
        "scoring_version": SCORING_VERSION,
        "config": asdict(config),
        "outcomes": [_canonical_outcome(row) for row in outcomes],
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(encoded).hexdigest()

# dusts off old reports in db and copies it onto the clean WorkerAssessment clipboard
def _result_from_record(
    record: TrustAssessment, *, platform_type: str
) -> WorkerAssessment:
    return WorkerAssessment(
        id=record.id,
        worker_id=record.worker_id,
        decision=record.decision,
        confidence=record.confidence,
        band=record.band,
        status=(
            "Building History"
            if record.status is AssessmentStatus.BUILDING_HISTORY
            else "Scored"
        ),
        signals_used=record.signals_used,
        explanation_summary=record.explanation_summary,
        platform_type_applied=platform_type,
    )


async def assess_worker(
    session: AsyncSession,
    worker_id: UUID,
    platform_type: str,
    *,
    job_context: dict[str, str] | None = None,
) -> WorkerAssessment:
    """Return one canonical assessment for all API and ingestion callers.

    Only verified persisted outcomes are scored. Request payloads are not used
    as evidence. A matching input/config fingerprint reuses the prior record.
    """

    if await session.get(Worker, worker_id) is None:
        raise UnknownWorkerError(f"Worker {worker_id} was not found")

    config = PRESETS.get(platform_type, PRESETS["generic"])
    outcomes = list(
        (
            await session.scalars(
                select(NormalizedOutcome)
                .where(
                    NormalizedOutcome.worker_id == worker_id,
                    NormalizedOutcome.verified.is_(True),
                )
                .order_by(NormalizedOutcome.occurred_at, NormalizedOutcome.id)
            )
        ).all()
    )

    fingerprint = _fingerprint(outcomes, platform_type, config)
    if job_context:
        fingerprint = hashlib.sha256(
            f"{fingerprint}:{json.dumps(job_context, sort_keys=True)}".encode()
        ).hexdigest()

    policy_name = f"platform:{platform_type if platform_type in PRESETS else 'generic'}"
    policy = await session.scalar(
        select(TrustPolicy).where(TrustPolicy.name == policy_name, TrustPolicy.version == 1)
    )
    if policy is None:
        policy = TrustPolicy(name=policy_name, version=1, is_active=True)
        session.add(policy)
        await session.flush()

    existing = await session.scalar(
        select(TrustAssessment).where(
            TrustAssessment.worker_id == worker_id,
            TrustAssessment.policy_id == policy.id,
            TrustAssessment.input_fingerprint == fingerprint,
        )
    )
    if existing is not None:
        return _result_from_record(
            existing,
            platform_type=platform_type,
        )

    tracked = set(config.weights)
    canonical_jobs = [normalise_db_row(row) for row in outcomes]
    signals, job_count = aggregate(canonical_jobs, tracked)
    result = score_worker(signals, job_count, config)

    if result["band"] == "Building History":
        status = AssessmentStatus.BUILDING_HISTORY
    elif result["decision"]:
        status = AssessmentStatus.APPROVED
    else:
        status = AssessmentStatus.RESTRICTED

    record = TrustAssessment(
        worker_id=worker_id,
        policy_id=policy.id,
        decision=result["decision"],
        confidence=Decimal(str(result["confidence"])),
        status=status,
        band=result["band"],
        signals_used=result["signals_used"],
        explanation_summary=result["explanation_summary"],
        input_fingerprint=fingerprint,
        assessed_at=datetime.now(UTC),
    )
    session.add(record)
    await session.flush()

    return WorkerAssessment(
        id=record.id,
        worker_id=record.worker_id,
        decision=record.decision,
        confidence=record.confidence,
        band=result["band"],
        status=result["status"],
        signals_used=result["signals_used"],
        explanation_summary=result["explanation_summary"],
        platform_type_applied=platform_type,
    )
