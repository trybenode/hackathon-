"""Verify persisted-history scoring and assessment reuse."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.domain import (
    NormalizedOutcome,
    OutcomeSource,
    OutcomeStatus,
    RawOutcome,
    TrustAssessment,
)
from app.services.trust_scoring import assessment as assessment_service


async def add_outcomes(session: AsyncSession, worker_id, count: int = 5) -> None:
    source = OutcomeSource(name=f"assessment-test-{uuid4()}", normalization_version="1")
    session.add(source)
    await session.flush()

    for index in range(count):
        raw = RawOutcome(
            source_id=source.id,
            external_outcome_id=f"job-{index}",
            payload={"status": "completed"},
            payload_checksum=f"{index:064x}",
        )
        session.add(raw)
        await session.flush()
        session.add(
            NormalizedOutcome(
                worker_id=worker_id,
                raw_outcome_id=raw.id,
                outcome_key=f"job-{index}",
                status=OutcomeStatus.COMPLETED,
                occurred_at=datetime.now(UTC) - timedelta(days=index),
                normalization_version="1",
                cancelled_by=None,
                dispute_resolution="dismissed",
                client_id=f"client-{index // 2}",
                source_platform="test-platform",
                import_method="api",
                verified=True,
                quality_flags=[],
            )
        )
    await session.flush()


@pytest.mark.asyncio
async def test_assess_worker_scores_persisted_verified_history(
    session: AsyncSession, worker
) -> None:
    await add_outcomes(session, worker.id)

    result = await assessment_service.assess_worker(session, worker.id, "generic")

    assert result.worker_id == worker.id
    assert result.decision is True
    assert result.band == "High"
    assert result.confidence > 0
    assert result.status == "Scored"


@pytest.mark.asyncio
async def test_assess_worker_reuses_assessment_when_inputs_unchanged(
    session: AsyncSession, worker, monkeypatch: pytest.MonkeyPatch
) -> None:
    await add_outcomes(session, worker.id)
    original_scorer = assessment_service.score_worker
    calls = 0

    def counted_scorer(*args, **kwargs):
        nonlocal calls
        calls += 1
        return original_scorer(*args, **kwargs)

    monkeypatch.setattr(assessment_service, "score_worker", counted_scorer)
    first = await assessment_service.assess_worker(session, worker.id, "generic")
    second = await assessment_service.assess_worker(session, worker.id, "generic")

    assessment_count = await session.scalar(
        select(func.count()).select_from(TrustAssessment)
    )
    assert calls == 1
    assert assessment_count == 1
    assert second.id == first.id
