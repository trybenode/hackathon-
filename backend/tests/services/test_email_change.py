"""Purpose: Verify an account can move to a new email address it proves it reads.

Dependencies: pytest, SQLAlchemy async sessions, app.services.auth.
Used by: the backend test suite and CI.
"""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.domain import User
from app.services import auth as service

NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


async def person(session: AsyncSession, email: str = "alex@company.com") -> User:
    user = User(email=email, display_name="Alex")
    session.add(user)
    await session.flush()
    return user


async def test_the_new_address_takes_over_once_its_code_checks_out(session: AsyncSession) -> None:
    user = await person(session)

    code = await service.request_email_change(session, user, "Alex@NewCo.io", now=NOW)
    changed = await service.confirm_email_change(session, user, "alex@newco.io", code, now=NOW + timedelta(minutes=1))

    assert changed.email == "alex@newco.io"


async def test_a_wrong_code_changes_nothing(session: AsyncSession) -> None:
    user = await person(session)
    await service.request_email_change(session, user, "alex@newco.io", now=NOW)

    with pytest.raises(service.InvalidCodeError):
        await service.confirm_email_change(session, user, "alex@newco.io", "000000", now=NOW)
    assert user.email == "alex@company.com"


@pytest.mark.parametrize("address", ["alex@company.com", "taken@company.com"])
async def test_an_address_in_use_is_refused(session: AsyncSession, address: str) -> None:
    user = await person(session)
    await person(session, "taken@company.com")

    with pytest.raises(service.EmailTakenError):
        await service.request_email_change(session, user, address, now=NOW)


async def test_a_code_for_one_address_cannot_move_to_another(session: AsyncSession) -> None:
    user = await person(session)
    code = await service.request_email_change(session, user, "alex@newco.io", now=NOW)

    with pytest.raises(service.InvalidCodeError):
        await service.confirm_email_change(session, user, "someone@else.io", code, now=NOW)
