"""Verify portable credential imports persist signed outcomes idempotently."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.domain import NormalizedOutcome
from app.services.credentials import import_credentials, sign_bundle


@pytest.mark.asyncio
async def test_signed_credential_import_persists_once(
    session: AsyncSession, worker
) -> None:
    now = datetime.now(UTC)
    token = sign_bundle(
        {
            "jti": str(uuid4()),
            "sub": str(worker.id),
            "outcomes": [
                {
                    "outcome_id": str(uuid4()),
                    "outcome_key": "outside-job-1",
                    "job_id": None,
                    "source_platform": "partner-platform",
                    "status": "completed",
                    "occurred_at": now.isoformat(),
                    "rating": 4.5,
                    "cancelled_by": None,
                    "dispute_resolution": "dismissed",
                    "flags": [],
                }
            ],
        },
        "s" * 32,
        now=now,
        lifetime=timedelta(days=1),
    )

    imported = await import_credentials(
        session, worker.id, token, "partner-platform", "s" * 32, now=now
    )
    replayed = await import_credentials(
        session, worker.id, token, "partner-platform", "s" * 32, now=now
    )
    outcomes = list(
        (
            await session.scalars(
                select(NormalizedOutcome).where(
                    NormalizedOutcome.worker_id == worker.id
                )
            )
        ).all()
    )

    assert imported == 1
    assert replayed == 0
    assert len(outcomes) == 1
    assert outcomes[0].source_platform == "partner-platform"
    assert outcomes[0].outcome_key == "outside-job-1"
    assert outcomes[0].verified is True
    assert outcomes[0].import_method == "api"
