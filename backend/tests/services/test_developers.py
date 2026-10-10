"""Purpose: Verify developer verification, operator review, credentials and name changes.

Dependencies: pytest, SQLAlchemy async sessions, app.services.developers.
Used by: the backend test suite and CI.
"""

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.developer import ApiRequestLog, ReviewStatus
from app.models.domain import Organization, OrganizationType, User, Worker
from app.services import developers as service
from app.services.portability import digest

DOC = ("id.pdf", b"%PDF-1.4 id")


async def developer(session: AsyncSession) -> User:
    user = User(email="dev@acme.io", display_name="")
    session.add(user)
    await session.flush()
    await service.ensure_developer(session, user)
    return user


async def submitted(session: AsyncSession) -> User:
    user = await developer(session)
    await service.submit_identity(session, user, full_name="Alex Morgan", document_type="national_id", document=DOC)
    await service.submit_business(
        session, user, business_name="Energies Technologies Ltd.", business_type="limited_liability_company",
        registration_number="RC1234567", tax_id="12345678-0001", document=("cac.pdf", b"%PDF-1.4 cac"),
    )
    return user


async def approved(session: AsyncSession) -> User:
    user = await submitted(session)
    await service.approve(session, await service.account_for(session, user))
    return user


async def test_sign_up_makes_one_profile(session: AsyncSession) -> None:
    user = await developer(session)
    first = await service.account_for(session, user)

    assert (await service.ensure_developer(session, user)).id == first.id
    assert first.kyb_status is ReviewStatus.NOT_STARTED


async def test_business_needs_the_identity_step_first(session: AsyncSession) -> None:
    user = await developer(session)

    with pytest.raises(service.StepOutOfOrderError):
        await service.submit_business(
            session, user, business_name="Acme", business_type="limited_liability_company",
            registration_number="RC1", tax_id="1", document=DOC,
        )


async def test_submission_goes_under_review(session: AsyncSession) -> None:
    account = await service.account_for(session, await submitted(session))

    assert account.kyc_status is ReviewStatus.UNDER_REVIEW
    assert account.kyb_status is ReviewStatus.UNDER_REVIEW
    assert account.submitted_at is not None


async def test_a_submission_under_review_cannot_be_changed(session: AsyncSession) -> None:
    user = await submitted(session)

    with pytest.raises(service.StepOutOfOrderError):
        await service.submit_identity(session, user, full_name="Someone Else", document_type="national_id", document=DOC)


async def test_unknown_choices_are_refused(session: AsyncSession) -> None:
    user = await developer(session)

    with pytest.raises(service.InvalidChoiceError):
        await service.submit_identity(session, user, full_name="Alex", document_type="library_card", document=DOC)


async def test_approval_makes_the_platform_organization(session: AsyncSession) -> None:
    user = await approved(session)
    account = await service.account_for(session, user)
    organization = await session.get(Organization, account.organization_id)

    assert account.kyb_status is ReviewStatus.APPROVED and account.kyc_status is ReviewStatus.APPROVED
    assert organization.name == "Energies Technologies Ltd."
    assert organization.organization_type is OrganizationType.PLATFORM
    assert user.display_name == "Alex Morgan"


async def test_a_rejected_developer_can_submit_again(session: AsyncSession) -> None:
    user = await submitted(session)
    account = await service.account_for(session, user)
    await service.reject(session, account, "The CAC certificate is unreadable.")

    assert account.kyb_status is ReviewStatus.REJECTED
    assert account.review_note == "The CAC certificate is unreadable."
    await service.submit_identity(session, user, full_name="Alex Morgan", document_type="national_id", document=DOC)


async def test_credentials_wait_for_approval(session: AsyncSession) -> None:
    user = await submitted(session)

    with pytest.raises(service.StepOutOfOrderError):
        await service.generate_credentials(session, user, "sandbox")


async def test_credentials_are_platform_keys_with_a_secret_shown_once(session: AsyncSession) -> None:
    user = await approved(session)

    key, secret = await service.generate_credentials(session, user, "production")

    assert key.key_id.startswith("pk_live_")
    assert secret.startswith("sk_live_")
    assert key.key_hash == digest(secret)
    assert key.environment == "production"
    assert key.can_attest is False
    assert [k.id for k in await service.credentials(session, await service.account_for(session, user))] == [key.id]


async def test_a_sandbox_key_brings_the_demo_workers(session: AsyncSession) -> None:
    user = await approved(session)

    key, secret = await service.generate_credentials(session, user, "sandbox")

    assert key.key_id.startswith("pk_sandbox_") and secret.startswith("sk_sandbox_")
    demos = await session.scalar(select(func.count()).select_from(Worker).where(Worker.is_sandbox.is_(True)))
    assert demos == 4


async def test_usage_counts_the_platform_calls(session: AsyncSession) -> None:
    user = await approved(session)
    key, _ = await service.generate_credentials(session, user, "sandbox")
    for status in (200, 201, 404):
        session.add(ApiRequestLog(platform_key_id=key.id, organization_id=key.organization_id, method="GET",
                                  path="/api/v1/trust/query", status_code=status, duration_ms=12))
    await session.flush()

    usage = await service.usage(session, await service.account_for(session, user))

    assert (usage.total_calls, usage.successful_calls) == (3, 2)
    assert len(usage.recent) == 3
    # Fourteen days for the chart, today last, holding today's calls.
    assert len(usage.daily) == service.CHART_DAYS
    assert (usage.daily[-1].total, usage.daily[-1].successful) == (3, 2)
    assert all(day.total == 0 for day in usage.daily[:-1])


async def test_name_change_needs_a_verified_name_and_one_at_a_time(session: AsyncSession) -> None:
    pending = await submitted(session)
    with pytest.raises(service.StepOutOfOrderError):
        await service.request_name_change(session, pending, new_name="Alex D. Morgan", reason="correction", document=None)

    account = await service.account_for(session, pending)
    await service.approve(session, account)
    request = await service.request_name_change(session, pending, new_name="Alex Daniel Morgan", reason="correction", document=None)
    assert request.current_name == "Alex Morgan"
    with pytest.raises(service.StepOutOfOrderError):
        await service.request_name_change(session, pending, new_name="A. Morgan", reason="other", document=None)

    await service.review_name_change(session, request, approved=True)
    assert account.full_name == "Alex Daniel Morgan"
    assert pending.display_name == "Alex Daniel Morgan"
