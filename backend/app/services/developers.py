"""Purpose: Run a developer from sign-up through verification to API credentials.

Dependencies: SQLAlchemy async sessions, app.models (developer, domain,
portability), document storage, and app.services.sandbox.
Used by: the developer dashboard endpoints, sign-up, and the operator's
review script (scripts/review_developer.py).

Verification is two steps, identity (KYC) then business (KYB), reviewed
together by an operator. Approval makes the developer's platform
organization; credentials are platform keys for it, sandbox or production.
Documents go to object storage and only their keys are kept.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from uuid import UUID
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.developer import ApiRequestLog, DeveloperAccount, NameChangeRequest, ReviewStatus
from app.models.domain import Organization, OrganizationType, User
from app.core.platform_auth import SCOPES
from app.models.portability import PlatformKey
from app.services import document_store as document_store_module
from app.services import sandbox
from app.services.document_store import DocumentStore
from app.services.portability import digest

DOCUMENT_TYPES = {
    "international_passport": "International passport",
    "national_id": "National ID card (NIN)",
    "drivers_licence": "Driver's licence",
    "voters_card": "Voter's card",
}
BUSINESS_TYPES = {
    "limited_liability_company": "Limited liability company",
    "business_name": "Registered business name",
    "other_entity": "Other registered entity",
}
NAME_CHANGE_REASONS = {
    "correction": "Correction of spelling or error",
    "legal_change": "Legal name change",
    "other": "Other reason",
}
ENVIRONMENTS = {"sandbox": "sandbox", "production": "live"}
#: Active keys a platform may hold per environment; room to rotate, not to hoard.
MAX_ACTIVE_KEYS = 5
#: How many recent calls the dashboard lists.
RECENT_CALLS = 10
#: Days of history the usage chart covers, today included.
CHART_DAYS = 14


class DeveloperError(Exception):
    """Base class for developer onboarding failures."""


class NotADeveloperError(DeveloperError):
    """The signed-in account has no developer profile."""


class StepOutOfOrderError(DeveloperError):
    """An earlier step is missing, or this one is already done or under review."""


class InvalidChoiceError(DeveloperError):
    """A value outside the listed options."""


class KeyNotFoundError(DeveloperError):
    """No active key of this developer's with that id."""


class LimitReachedError(DeveloperError):
    """Too many active keys in one environment."""


@dataclass(frozen=True)
class DailyUsage:
    day: date
    total: int
    successful: int


@dataclass(frozen=True)
class Usage:
    total_calls: int
    successful_calls: int
    recent: list[ApiRequestLog]
    #: One entry per day for the chart, oldest first, quiet days as zero.
    daily: list[DailyUsage]


def _now() -> datetime:
    return datetime.now(UTC)


async def ensure_developer(session: AsyncSession, user: User) -> DeveloperAccount:
    """The user's developer profile, made on first sign-up."""

    account = await session.scalar(select(DeveloperAccount).where(DeveloperAccount.user_id == user.id))
    if account is None:
        account = DeveloperAccount(
            user_id=user.id, kyc_status=ReviewStatus.NOT_STARTED, kyb_status=ReviewStatus.NOT_STARTED
        )
        session.add(account)
        await session.flush()
    return account


async def account_for(session: AsyncSession, user: User) -> DeveloperAccount:
    account = await session.scalar(select(DeveloperAccount).where(DeveloperAccount.user_id == user.id))
    if account is None:
        raise NotADeveloperError("This account has no developer profile.")
    return account


def identity_submitted(account: DeveloperAccount) -> bool:
    # Not the document reference: without a bucket (local work) none is kept.
    return bool(account.full_name and account.id_document_type)


def _open_to_submit(account: DeveloperAccount) -> None:
    if account.kyb_status is ReviewStatus.UNDER_REVIEW:
        raise StepOutOfOrderError("Your verification is under review.")
    if account.kyb_status is ReviewStatus.APPROVED:
        raise StepOutOfOrderError("Your business is already verified.")


async def _store(
    account: DeveloperAccount, document: tuple[str, bytes], kind: str, store: DocumentStore | None
) -> str | None:
    filename, content = document
    # Resolved at call time so tests can swap the bucket out.
    stored = await (store or document_store_module.default_document_store).store(
        filename=filename, content=content, prefix=f"developer-documents/{account.id}/{kind}"
    )
    return stored.reference or None


async def submit_identity(
    session: AsyncSession,
    user: User,
    *,
    full_name: str,
    document_type: str,
    document: tuple[str, bytes],
    document_store: DocumentStore | None = None,
) -> DeveloperAccount:
    """Step 1: who the developer is. Kept until the business step is submitted."""

    account = await account_for(session, user)
    _open_to_submit(account)
    if document_type not in DOCUMENT_TYPES:
        raise InvalidChoiceError("Choose one of the listed identity documents.")

    account.id_document_reference = await _store(account, document, "identity", document_store)
    account.full_name = full_name.strip()
    account.id_document_type = document_type
    await session.flush()
    return account


async def submit_business(
    session: AsyncSession,
    user: User,
    *,
    business_name: str,
    business_type: str,
    registration_number: str,
    tax_id: str,
    document: tuple[str, bytes],
    now: datetime | None = None,
    document_store: DocumentStore | None = None,
) -> DeveloperAccount:
    """Step 2: the registered business. Sends both steps for an operator's review."""

    account = await account_for(session, user)
    _open_to_submit(account)
    if not identity_submitted(account):
        raise StepOutOfOrderError("Verify your identity before your business.")
    if business_type not in BUSINESS_TYPES:
        raise InvalidChoiceError("Choose one of the listed business types.")

    account.cac_document_reference = await _store(account, document, "business", document_store)
    account.business_name = business_name.strip()
    account.business_type = business_type
    account.registration_number = registration_number.strip()
    account.tax_id = tax_id.strip()
    account.kyc_status = ReviewStatus.UNDER_REVIEW
    account.kyb_status = ReviewStatus.UNDER_REVIEW
    account.review_note = None
    account.submitted_at = now or _now()
    await session.flush()
    return account


async def approve(session: AsyncSession, account: DeveloperAccount, *, now: datetime | None = None) -> Organization:
    """An operator accepts the submission: the business becomes a platform."""

    if account.kyb_status is not ReviewStatus.UNDER_REVIEW:
        raise StepOutOfOrderError("Only a submission under review can be approved.")

    organization = await session.get(Organization, account.organization_id) if account.organization_id else None
    if organization is None:
        organization = Organization(name=account.business_name or "", organization_type=OrganizationType.PLATFORM)
        session.add(organization)
        await session.flush()
        account.organization_id = organization.id
    account.kyc_status = ReviewStatus.APPROVED
    account.kyb_status = ReviewStatus.APPROVED
    account.reviewed_at = now or _now()
    user = await session.get(User, account.user_id)
    if user is not None and account.full_name:
        user.display_name = account.full_name
    await session.flush()
    return organization


async def reject(
    session: AsyncSession, account: DeveloperAccount, note: str, *, now: datetime | None = None
) -> None:
    """An operator sends the submission back; the developer can submit again."""

    if account.kyb_status is not ReviewStatus.UNDER_REVIEW:
        raise StepOutOfOrderError("Only a submission under review can be rejected.")
    account.kyc_status = ReviewStatus.REJECTED
    account.kyb_status = ReviewStatus.REJECTED
    account.review_note = note.strip()[:500]
    account.reviewed_at = now or _now()
    await session.flush()


def _new_secret(environment: str) -> str:
    return f"sk_{ENVIRONMENTS[environment]}_{secrets.token_urlsafe(32)}"


def _clean_scopes(scopes: list[str] | None) -> list[str] | None:
    """None is full access; otherwise a non-empty choice of the known groups."""

    if scopes is None:
        return None
    unknown = sorted(set(scopes) - set(SCOPES))
    if unknown:
        raise InvalidChoiceError(f"Unknown access: {', '.join(unknown)}.")
    if not scopes:
        raise InvalidChoiceError("Choose at least one kind of access, or full access.")
    return sorted(set(scopes), key=list(SCOPES).index)


def _clean_name(name: str) -> str:
    cleaned = name.strip()
    if not 1 <= len(cleaned) <= 80:
        raise InvalidChoiceError("Give the key a name of up to 80 characters.")
    return cleaned


async def _approved(session: AsyncSession, user: User) -> DeveloperAccount:
    account = await account_for(session, user)
    if account.kyb_status is not ReviewStatus.APPROVED or account.organization_id is None:
        raise StepOutOfOrderError("Complete and receive approval for KYB to generate your API credentials.")
    return account


async def create_key(
    session: AsyncSession,
    user: User,
    *,
    environment: str,
    name: str = "API key",
    scopes: list[str] | None = None,
) -> tuple[PlatformKey, str]:
    """A new key for the developer's platform; the secret is returned only here.

    The secret is what goes in X-API-Key. A sandbox key also makes sure the
    demo workers exist, so the first call has someone to look up.
    """

    account = await _approved(session, user)
    if environment not in ENVIRONMENTS:
        raise InvalidChoiceError("Choose Sandbox or Production.")
    active = await session.scalar(
        select(func.count())
        .select_from(PlatformKey)
        .where(
            PlatformKey.organization_id == account.organization_id,
            PlatformKey.environment == environment,
            PlatformKey.revoked_at.is_(None),
        )
    )
    if active >= MAX_ACTIVE_KEYS:
        raise LimitReachedError(
            f"You can have up to {MAX_ACTIVE_KEYS} active {environment} keys. Revoke one you no longer use."
        )

    secret = _new_secret(environment)
    key = PlatformKey(
        organization_id=account.organization_id,
        key_hash=digest(secret),
        environment=environment,
        key_id=f"pk_{ENVIRONMENTS[environment]}_{secrets.token_hex(8)}",
        created_by_user_id=user.id,
        name=_clean_name(name),
        scopes=_clean_scopes(scopes),
    )
    session.add(key)
    if environment == sandbox.SANDBOX:
        await sandbox.ensure_demo_workers(session)
    await session.flush()
    return key, secret


async def credentials(session: AsyncSession, account: DeveloperAccount) -> list[PlatformKey]:
    """The platform's active keys, newest first; revoked keys are hidden."""

    if account.organization_id is None:
        return []
    return list(
        (
            await session.scalars(
                select(PlatformKey)
                .where(PlatformKey.organization_id == account.organization_id, PlatformKey.revoked_at.is_(None))
                .order_by(PlatformKey.created_at.desc())
            )
        ).all()
    )


async def key_for(session: AsyncSession, user: User, key: UUID) -> PlatformKey:
    """One of the developer's active keys."""

    account = await _approved(session, user)
    found = await session.get(PlatformKey, key)
    if found is None or found.organization_id != account.organization_id or found.revoked_at is not None:
        raise KeyNotFoundError("No active API key with that id.")
    return found


async def update_key(
    session: AsyncSession, user: User, key: UUID, *, name: str, scopes: list[str] | None
) -> PlatformKey:
    """Rename a key and set its access; `scopes=None` is full access."""

    found = await key_for(session, user, key)
    found.name = _clean_name(name)
    found.scopes = _clean_scopes(scopes)
    await session.flush()
    return found


async def rotate_key(session: AsyncSession, user: User, key: UUID) -> tuple[PlatformKey, str]:
    """A new secret for the same key; the old secret stops working at once."""

    found = await key_for(session, user, key)
    secret = _new_secret(found.environment)
    found.key_hash = digest(secret)
    await session.flush()
    return found, secret


async def revoke_key(session: AsyncSession, user: User, key: UUID, *, now: datetime | None = None) -> None:
    found = await key_for(session, user, key)
    found.revoked_at = now or _now()
    await session.flush()


async def calls_per_key(session: AsyncSession, account: DeveloperAccount, *, now: datetime | None = None) -> dict[UUID, int]:
    """Calls each key made over the chart's window."""

    if account.organization_id is None:
        return {}
    since = (now or _now()) - timedelta(days=CHART_DAYS)
    rows = await session.execute(
        select(ApiRequestLog.platform_key_id, func.count())
        .where(ApiRequestLog.organization_id == account.organization_id, ApiRequestLog.created_at >= since)
        .group_by(ApiRequestLog.platform_key_id)
    )
    return {key: count for key, count in rows.all()}


async def usage(session: AsyncSession, account: DeveloperAccount, *, now: datetime | None = None) -> Usage:
    """Calls made with the platform's keys: totals, the latest few, and per day."""

    today = (now or _now()).date()
    days = [today - timedelta(days=offset) for offset in range(CHART_DAYS - 1, -1, -1)]
    if account.organization_id is None:
        return Usage(0, 0, [], [DailyUsage(day, 0, 0) for day in days])
    mine = ApiRequestLog.organization_id == account.organization_id
    total = await session.scalar(select(func.count()).select_from(ApiRequestLog).where(mine))
    ok = await session.scalar(
        select(func.count())
        .select_from(ApiRequestLog)
        .where(mine, ApiRequestLog.status_code >= 200, ApiRequestLog.status_code < 300)
    )
    recent = (
        await session.scalars(
            select(ApiRequestLog).where(mine).order_by(ApiRequestLog.created_at.desc()).limit(RECENT_CALLS)
        )
    ).all()
    # Counted per UTC day in the database; date() works on SQLite and Postgres.
    day = func.date(ApiRequestLog.created_at)
    success = func.sum(case((ApiRequestLog.status_code.between(200, 299), 1), else_=0))
    counts = {
        str(row.day): (row.total, row.successful or 0)
        for row in await session.execute(
            select(day.label("day"), func.count().label("total"), success.label("successful"))
            .where(mine, ApiRequestLog.created_at >= datetime.combine(days[0], datetime.min.time(), UTC))
            .group_by(day)
        )
    }
    daily = [DailyUsage(d, *counts.get(d.isoformat(), (0, 0))) for d in days]
    return Usage(total or 0, ok or 0, list(recent), daily)


async def open_name_change(session: AsyncSession, account: DeveloperAccount) -> NameChangeRequest | None:
    return await session.scalar(
        select(NameChangeRequest).where(
            NameChangeRequest.account_id == account.id,
            NameChangeRequest.status == ReviewStatus.UNDER_REVIEW,
        )
    )


async def request_name_change(
    session: AsyncSession,
    user: User,
    *,
    new_name: str,
    reason: str,
    document: tuple[str, bytes] | None,
    document_store: DocumentStore | None = None,
) -> NameChangeRequest:
    """Ask to correct the verified name; an operator reviews it."""

    account = await account_for(session, user)
    if account.kyc_status is not ReviewStatus.APPROVED or not account.full_name:
        raise StepOutOfOrderError("Your name can be changed once your identity is verified.")
    if reason not in NAME_CHANGE_REASONS:
        raise InvalidChoiceError("Choose one of the listed reasons.")
    if await open_name_change(session, account):
        raise StepOutOfOrderError("You already have a name change under review.")

    request = NameChangeRequest(
        account_id=account.id,
        current_name=account.full_name,
        new_name=new_name.strip(),
        reason=reason,
        document_reference=await _store(account, document, "name-change", document_store) if document else None,
        status=ReviewStatus.UNDER_REVIEW,
    )
    session.add(request)
    await session.flush()
    return request


async def review_name_change(
    session: AsyncSession, request: NameChangeRequest, *, approved: bool, now: datetime | None = None
) -> None:
    """An operator decides; approval updates the verified name everywhere."""

    if request.status is not ReviewStatus.UNDER_REVIEW:
        raise StepOutOfOrderError("This request has already been reviewed.")
    request.status = ReviewStatus.APPROVED if approved else ReviewStatus.REJECTED
    request.reviewed_at = now or _now()
    if approved:
        account = await session.get(DeveloperAccount, request.account_id)
        account.full_name = request.new_name
        user = await session.get(User, account.user_id)
        user.display_name = request.new_name
    await session.flush()
