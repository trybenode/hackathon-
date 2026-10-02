"""Purpose: Verify overdue guarantor instruments actually expire.

Dependencies: pytest, SQLAlchemy async sessions, and app.services.expiry.
Used by: the backend test suite and CI.

The sweep is the only thing that moves an instrument to Expired, so FR-4.4
depends on it running.
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.domain import AgreementStatus, GuarantorAgreement, User, Worker
from app.services import expiry as service

NOW = datetime.now(tz=UTC)


def build_agreement(worker: Worker, guarantor: User, *, valid_until: datetime) -> GuarantorAgreement:
    return GuarantorAgreement(
        worker_id=worker.id,
        guarantor_user_id=guarantor.id,
        scope="Cleaning",
        conditions="Covers no-show.",
        relationship_type="sibling",
        status=AgreementStatus.ACTIVE,
        valid_until=valid_until,
        signed_at=NOW - timedelta(days=30),
        verified_at=NOW - timedelta(days=30),
    )


async def test_sweep_expires_only_overdue_instruments(
    session: AsyncSession, worker: Worker
) -> None:
    guarantor = User(email="grace@example.com", display_name="Grace G")
    session.add(guarantor)
    await session.flush()

    overdue = build_agreement(worker, guarantor, valid_until=NOW - timedelta(days=1))
    current = build_agreement(worker, guarantor, valid_until=NOW + timedelta(days=30))
    session.add_all([overdue, current])
    await session.flush()

    # The sweep manages its own session, so hand it one that yields this one.
    class _Factory:
        def __call__(self):
            return _Session()

    class _Session:
        async def __aenter__(self):
            return session

        async def __aexit__(self, *_):
            return False

    expired = await service.run_sweep(_Factory())

    assert expired == 1
    assert overdue.status is AgreementStatus.EXPIRED
    assert current.status is AgreementStatus.ACTIVE
