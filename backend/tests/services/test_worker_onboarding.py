"""Purpose: Verify a new worker's sign-up, identity and liveness checks, and guarantor invite.

Dependencies: pytest, SQLAlchemy async sessions, and app.services.worker_onboarding.
Used by: the backend test suite and CI.
"""

from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.domain import AgreementStatus, IdentityVerification, User, Worker
from app.services import guarantor as guarantor_service
from app.services import worker_onboarding as service
from tests.services.test_guarantor import build_frame, build_signature, build_submission

NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


async def new_worker(session: AsyncSession) -> User:
    user = User(email="new@example.com", display_name="")
    session.add(user)
    await session.flush()
    await service.ensure_worker(session, user)
    return user


def details(**overrides):
    fields = {"first_name": "Jane", "last_name": "Adams", "date_of_birth": date(1995, 4, 2)}
    fields.update(overrides)
    return build_submission(**fields)


async def verified(session: AsyncSession) -> User:
    user = await new_worker(session)
    await service.submit_identity(session, user, details())
    await service.complete_liveness(session, user, build_frame())
    return user


async def test_sign_up_makes_one_worker_profile(session: AsyncSession) -> None:
    user = await new_worker(session)
    await service.ensure_worker(session, user)

    count = await session.scalar(select(func.count()).select_from(Worker).where(Worker.user_id == user.id))
    assert count == 1
    assert (await service.status(session, user)).next_step == "identity"


async def test_identity_puts_the_details_on_the_account(session: AsyncSession) -> None:
    user = await new_worker(session)

    record = await service.submit_identity(session, user, details())

    assert record.status == "verified"
    assert user.display_name == "Jane Adams"
    assert user.phone == "+2348012345678"
    assert user.address == "12 Trust Street, Lagos"
    assert (await service.status(session, user)).next_step == "liveness"


async def test_failed_identity_is_recorded_and_changes_nothing(session: AsyncSession) -> None:
    user = await new_worker(session)

    with pytest.raises(service.CheckFailedError):
        await service.submit_identity(session, user, details(nin="123"))

    stored = await session.scalar(select(IdentityVerification).where(IdentityVerification.user_id == user.id))
    assert stored.status == "failed"
    assert user.display_name == ""
    # Only the provider's reference is kept, never the numbers.
    assert "123" not in stored.provider_reference


async def test_liveness_waits_for_identity(session: AsyncSession) -> None:
    user = await new_worker(session)

    with pytest.raises(service.StepOutOfOrderError):
        await service.complete_liveness(session, user, build_frame())


async def test_both_checks_lead_to_the_guarantor_step(session: AsyncSession) -> None:
    user = await verified(session)

    progress = await service.status(session, user)
    assert progress.identity_verified and progress.liveness_verified
    assert progress.next_step == "guarantor"
    assert progress.guarantor == "none"


async def test_guarantor_invite_needs_both_checks(session: AsyncSession) -> None:
    user = await new_worker(session)

    with pytest.raises(service.StepOutOfOrderError):
        await service.invite_guarantor(session, user, first_name="Hannah", last_name="Lazarus", relationship="employer")


async def test_invite_shows_as_pending_until_the_guarantor_verifies(session: AsyncSession) -> None:
    user = await verified(session)

    invite = await service.invite_guarantor(
        session, user, first_name="Hannah", last_name="Lazarus", relationship="employer", now=NOW
    )

    assert invite.name == "Hannah Lazarus"
    assert invite.status == "Pending Signature"
    assert invite.expires_at == NOW + timedelta(days=7)
    progress = await service.status(session, user, now=NOW)
    assert progress.guarantor == "pending"
    assert progress.next_step is None


async def test_an_active_guarantee_unlocks_the_worker(session: AsyncSession) -> None:
    user = await verified(session)
    invite = await service.invite_guarantor(
        session, user, first_name="Hannah", last_name="Lazarus", relationship="employer", now=NOW
    )
    hannah = User(email="hannah@example.com", display_name="")
    session.add(hannah)
    await session.flush()

    await guarantor_service.claim_invite(session, invite.instrument_id, hannah)
    await guarantor_service.sign_instrument(
        session, invite.instrument_id, build_signature(), now=NOW + timedelta(hours=1)
    )
    await guarantor_service.submit_identity_check(session, invite.instrument_id, build_submission())
    agreement = await guarantor_service.complete_liveness_check(session, invite.instrument_id, build_frame())

    worker = await session.scalar(select(Worker).where(Worker.user_id == user.id))
    assert agreement.status is AgreementStatus.ACTIVE
    assert await service.has_active_guarantor(session, worker)
    assert (await service.status(session, user)).guarantor == "active"


async def test_an_expired_invite_no_longer_counts(session: AsyncSession) -> None:
    user = await verified(session)
    await service.invite_guarantor(
        session, user, first_name="Hannah", last_name="Lazarus", relationship="employer", now=NOW
    )

    later = NOW + timedelta(days=8)
    assert (await service.status(session, user, now=later)).guarantor == "none"
