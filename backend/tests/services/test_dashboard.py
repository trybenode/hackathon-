"""Purpose: Verify the guarantor dashboard reads only that guarantor's rows.

Dependencies: pytest, SQLAlchemy async sessions, and app.services.dashboard.
Used by: the backend test suite and CI.
"""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.domain import AgreementStatus, AuditEvent, GuarantorAgreement, User, Worker
from app.services import dashboard as service

NOW = datetime.now(tz=UTC)


async def build_guarantee(
    session: AsyncSession,
    worker: Worker,
    guarantor: User,
    *,
    agreement_status: AgreementStatus = AgreementStatus.ACTIVE,
    valid_days: int = 60,
) -> GuarantorAgreement:
    agreement = GuarantorAgreement(
        worker_id=worker.id,
        guarantor_user_id=guarantor.id,
        scope="Cleaning",
        conditions="Covers no-show.",
        relationship_type="sibling",
        status=agreement_status,
        valid_until=NOW + timedelta(days=valid_days),
        signed_at=NOW - timedelta(days=3),
        verified_at=NOW - timedelta(days=3),
    )
    if agreement_status is AgreementStatus.EXPIRED:
        agreement.closed_at = agreement.valid_until
    session.add(agreement)
    await session.flush()
    return agreement


async def make_guarantor(session: AsyncSession, email: str = "grace@example.com") -> User:
    guarantor = User(email=email, display_name="Grace G")
    session.add(guarantor)
    await session.flush()
    return guarantor


async def test_active_and_expired_tabs(session: AsyncSession, worker: Worker) -> None:
    """A guarantee lasts a year; once it runs out it moves to Expired."""

    guarantor = await make_guarantor(session)
    active = await build_guarantee(session, worker, guarantor)
    expired = await build_guarantee(
        session, worker, guarantor, agreement_status=AgreementStatus.EXPIRED, valid_days=-5
    )

    summary = await service.load_summary(session, guarantor.id)
    by_id = {card.instrument_id: card for card in summary.guarantees}

    assert by_id[active.id].bucket == "active"
    assert by_id[expired.id].bucket == "expired"
    assert by_id[expired.id].ended_on == expired.closed_at
    assert summary.active_count == 1
    assert summary.completed_count == 1


async def test_card_carries_the_term(session: AsyncSession, worker: Worker) -> None:
    guarantor = await make_guarantor(session)
    agreement = await build_guarantee(session, worker, guarantor)

    card = (await service.load_summary(session, guarantor.id)).guarantees[0]

    assert card.started_on == agreement.verified_at
    assert card.valid_until == agreement.valid_until
    assert card.reference.startswith("G-")
    assert card.status == "Active"


@pytest.mark.parametrize(
    ("status", "bucket"),
    [
        # A running claim still needs the guarantor.
        (AgreementStatus.TRIGGERED, "active"),
        (AgreementStatus.DISPUTED, "active"),
        (AgreementStatus.SUSPENDED, "active"),
        # Over, but not by running out the year: shown only under All.
        (AgreementStatus.PAID, "closed"),
        (AgreementStatus.DISMISSED, "closed"),
        (AgreementStatus.REVOKED, "closed"),
        (AgreementStatus.DECLINED, "closed"),
        # Waiting on the guarantor.
        (AgreementStatus.PENDING_SIGNATURE, "pending"),
        (AgreementStatus.PENDING_VERIFICATION, "pending"),
    ],
)
async def test_bucket_follows_the_instrument_alone(
    session: AsyncSession, worker: Worker, status: AgreementStatus, bucket: str
) -> None:
    guarantor = await make_guarantor(session)
    await build_guarantee(session, worker, guarantor, agreement_status=status)

    card = (await service.load_summary(session, guarantor.id)).guarantees[0]

    assert card.bucket == bucket
    # The card still says what actually happened.
    assert card.status == service.status_label(status)


async def test_summary_is_scoped_to_one_guarantor(
    session: AsyncSession, worker: Worker
) -> None:
    mine = await make_guarantor(session, "mine@example.com")
    theirs = await make_guarantor(session, "theirs@example.com")

    await build_guarantee(session, worker, theirs)

    summary = await service.load_summary(session, mine.id)

    assert summary.guarantees == []
    assert summary.active_count == 0


async def test_action_required_picks_the_waiting_request(
    session: AsyncSession, worker: Worker
) -> None:
    guarantor = await make_guarantor(session)
    await build_guarantee(
        session, worker, guarantor, agreement_status=AgreementStatus.PENDING_SIGNATURE
    )

    summary = await service.load_summary(session, guarantor.id)

    assert summary.action_required is not None
    assert summary.action_required.status == "Pending Signature"


async def test_guarantee_detail_has_its_own_history(
    session: AsyncSession, worker: Worker
) -> None:
    guarantor = await make_guarantor(session)
    agreement = await build_guarantee(session, worker, guarantor)
    other = await build_guarantee(session, worker, guarantor)
    session.add_all(
        [
            AuditEvent(
                entity_type="guarantor_agreement",
                entity_id=agreement.id,
                action="guarantor.identity_verified",
                event_metadata={},
            ),
            AuditEvent(
                entity_type="guarantor_agreement",
                entity_id=agreement.id,
                action="guarantor.activated",
                event_metadata={},
            ),
            AuditEvent(
                entity_type="guarantor_agreement",
                entity_id=other.id,
                action="guarantor.expired",
                event_metadata={},
            ),
        ]
    )
    await session.flush()

    detail = await service.load_guarantee(session, guarantor.id, agreement.id)

    assert {entry.label for entry in detail.activity} == {
        "Identity verified",
        "Guarantee activated",
    }
    assert detail.relationship == "sibling"
    assert detail.card.instrument_id == agreement.id
    assert any("Cleaning" in paragraph for paragraph in detail.agreement)
    assert "one year" in detail.agreement[0]


async def test_guarantee_detail_hides_other_guarantors(
    session: AsyncSession, worker: Worker
) -> None:
    mine = await make_guarantor(session, "mine@example.com")
    theirs = await make_guarantor(session, "theirs@example.com")
    agreement = await build_guarantee(session, worker, theirs)

    with pytest.raises(service.GuaranteeNotFoundError):
        await service.load_guarantee(session, mine.id, agreement.id)


async def test_notifications_sort_without_timezone_errors(
    session: AsyncSession, worker: Worker
) -> None:
    """Stored timestamps are naive on SQLite and aware on Postgres."""

    guarantor = await make_guarantor(session)

    # One expiring soon and one far off, so both branches are built and sorted.
    await build_guarantee(session, worker, guarantor, valid_days=3)
    await build_guarantee(session, worker, guarantor, valid_days=300)

    items = await service.load_notifications(session, guarantor.id)

    assert any(item.icon == "calendar" for item in items)
    assert [item.at for item in items] == sorted((item.at for item in items), reverse=True)
