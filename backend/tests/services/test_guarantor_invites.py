"""Purpose: Verify worker invite links and how a guarantor claims one.

Dependencies: pytest, SQLAlchemy async sessions, and app.services.guarantor.
Used by: the backend test suite and CI.
"""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.domain import AgreementStatus, User, Worker
from app.services import guarantor as service
from tests.services.test_guarantor import build_frame, build_signature, build_submission

NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


async def invite(session: AsyncSession, worker: Worker, **overrides):
    fields = {"first_name": "Hannah", "last_name": "Lazarus", "relationship": "employer"}
    fields.update(overrides)
    return await service.invite_guarantor(session, worker, now=NOW, **fields)


async def person(session: AsyncSession, email: str, name: str = "") -> User:
    user = User(email=email, display_name=name)
    session.add(user)
    await session.flush()
    return user


async def test_invite_waits_a_week_for_someone_to_claim_it(
    session: AsyncSession, worker: Worker
) -> None:
    agreement = await invite(session, worker)

    assert agreement.guarantor_user_id is None
    assert agreement.guarantor_name == "Hannah Lazarus"
    assert agreement.relationship_type == "employer"
    assert agreement.status is AgreementStatus.PENDING_SIGNATURE
    assert agreement.valid_until == NOW + timedelta(days=7)


async def test_a_new_invite_withdraws_the_unclaimed_one(
    session: AsyncSession, worker: Worker
) -> None:
    first = await invite(session, worker)
    second = await invite(session, worker, first_name="Ada")

    assert first.status is AgreementStatus.REVOKED
    assert second.status is AgreementStatus.PENDING_SIGNATURE


async def test_claiming_names_the_guarantor(session: AsyncSession, worker: Worker) -> None:
    agreement = await invite(session, worker)
    hannah = await person(session, "hannah@example.com")

    claimed = await service.claim_invite(session, agreement.id, hannah)

    assert claimed.guarantor_user_id == hannah.id
    # A brand-new account takes the name the worker gave.
    assert hannah.display_name == "Hannah Lazarus"
    # Claiming again is harmless.
    await service.claim_invite(session, agreement.id, hannah)


async def test_only_one_person_can_claim(session: AsyncSession, worker: Worker) -> None:
    agreement = await invite(session, worker)
    await service.claim_invite(session, agreement.id, await person(session, "a@example.com"))

    with pytest.raises(service.InviteClaimedError):
        await service.claim_invite(session, agreement.id, await person(session, "b@example.com"))


async def test_a_worker_cannot_claim_their_own_invite(
    session: AsyncSession, worker: Worker
) -> None:
    agreement = await invite(session, worker)
    own = await session.get(User, worker.user_id)

    with pytest.raises(service.SelfGuaranteeError):
        await service.claim_invite(session, agreement.id, own)


async def test_an_unclaimed_invite_cannot_be_signed(
    session: AsyncSession, worker: Worker
) -> None:
    agreement = await invite(session, worker)

    with pytest.raises(service.UnclaimedInviteError):
        await service.sign_instrument(session, agreement.id, build_signature(), now=NOW + timedelta(hours=1))


async def test_a_claimed_invite_runs_the_usual_checks(
    session: AsyncSession, worker: Worker
) -> None:
    agreement = await invite(session, worker)
    hannah = await person(session, "hannah@example.com")
    await service.claim_invite(session, agreement.id, hannah)

    await service.sign_instrument(session, agreement.id, build_signature(), now=NOW + timedelta(hours=1))
    await service.submit_identity_check(session, agreement.id, build_submission())
    active = await service.complete_liveness_check(session, agreement.id, build_frame())

    assert active.status is AgreementStatus.ACTIVE
    assert active.guarantor_user_id == hannah.id
