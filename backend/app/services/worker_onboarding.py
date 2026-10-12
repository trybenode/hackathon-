"""Purpose: Take a new worker from sign-up to a verified profile with a guarantor.

Dependencies: SQLAlchemy async sessions, app.models.domain, the identity
provider seam, document storage, and app.services.guarantor for invites.
Used by: the auth endpoints (sign-up and where to land) and the onboarding
endpoints behind the worker's verification screens.

The steps run in order: identity details, then the liveness check, then an
invite link for a guarantor. Identity numbers and the selfie go to the
provider and are dropped; only references are stored, as for guarantors.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.domain import AgreementStatus, GuarantorAgreement, IdentityVerification, User, Worker
from app.services import document_store as document_store_module
from app.services import guarantor as guarantor_service
from app.services.document_store import DocumentStore
from app.services.identity_provider import (
    IdentityProvider,
    IdentitySubmission,
    LivenessProvider,
    LivenessSubmission,
    default_liveness_provider,
    default_provider,
)

#: A guarantee in one of these states is still waiting on the guarantor.
WAITING = {AgreementStatus.PENDING_SIGNATURE, AgreementStatus.PENDING_VERIFICATION}


class OnboardingError(Exception):
    """Base class for onboarding failures."""


class NotAWorkerError(OnboardingError):
    """The signed-in account has no worker profile."""


class StepOutOfOrderError(OnboardingError):
    """An earlier step has not been completed yet."""


class CheckFailedError(OnboardingError):
    """The provider did not pass the identity or liveness check."""


@dataclass(frozen=True)
class GuarantorInvite:
    instrument_id: UUID
    name: str
    relationship: str
    #: "Pending Signature", "Pending Verification" or "Active".
    status: str
    expires_at: datetime


@dataclass(frozen=True)
class OnboardingStatus:
    identity_verified: bool
    liveness_verified: bool
    #: "none", "pending" or "active".
    guarantor: str
    #: The guarantee waiting on, or held by, a guarantor.
    invite: GuarantorInvite | None

    @property
    def next_step(self) -> str | None:
        """The first unfinished step. The guarantor step can be skipped."""

        if not self.identity_verified:
            return "identity"
        if not self.liveness_verified:
            return "liveness"
        if self.guarantor == "none":
            return "guarantor"
        return None


def _now() -> datetime:
    return datetime.now(UTC)


def _as_aware(moment: datetime) -> datetime:
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)


async def ensure_worker(session: AsyncSession, user: User) -> Worker:
    """The user's worker profile, made on first sign-up."""

    worker = await session.scalar(select(Worker).where(Worker.user_id == user.id))
    if worker is None:
        worker = Worker(user_id=user.id)
        session.add(worker)
        await session.flush()
    return worker


async def _worker(session: AsyncSession, user: User) -> Worker:
    worker = await session.scalar(select(Worker).where(Worker.user_id == user.id))
    if worker is None:
        raise NotAWorkerError("This account has no worker profile.")
    return worker


async def _passed(session: AsyncSession, user: User, check_type: str) -> bool:
    """Whether the latest check of this kind passed; a later failure counts."""

    latest = await session.scalar(
        select(IdentityVerification)
        .where(IdentityVerification.user_id == user.id, IdentityVerification.check_type == check_type)
        .order_by(IdentityVerification.created_at.desc(), IdentityVerification.id.desc())
        .limit(1)
    )
    return latest is not None and latest.status == "verified"


async def current_guarantee(
    session: AsyncSession, worker: Worker, *, now: datetime | None = None
) -> GuarantorAgreement | None:
    """The live guarantee if there is one, else the newest one still waiting."""

    moment = now or _now()
    agreements = (
        await session.scalars(
            select(GuarantorAgreement)
            .where(
                GuarantorAgreement.worker_id == worker.id,
                GuarantorAgreement.status.in_({AgreementStatus.ACTIVE, *WAITING}),
            )
            .order_by(GuarantorAgreement.created_at.desc())
        )
    ).all()
    live = [item for item in agreements if _as_aware(item.valid_until) > moment]
    active = [item for item in live if item.status is AgreementStatus.ACTIVE]
    return (active or live or [None])[0]


async def has_active_guarantor(
    session: AsyncSession, worker: Worker, *, now: datetime | None = None
) -> bool:
    agreement = await current_guarantee(session, worker, now=now)
    return agreement is not None and agreement.status is AgreementStatus.ACTIVE


async def _invite_view(session: AsyncSession, agreement: GuarantorAgreement) -> GuarantorInvite:
    person = (
        await session.get(User, agreement.guarantor_user_id) if agreement.guarantor_user_id else None
    )
    return GuarantorInvite(
        instrument_id=agreement.id,
        name=(person.display_name if person else "") or agreement.guarantor_name or "",
        relationship=agreement.relationship_type,
        status=guarantor_service.status_label(agreement.status),
        expires_at=_as_aware(agreement.valid_until),
    )


async def status(session: AsyncSession, user: User, *, now: datetime | None = None) -> OnboardingStatus:
    worker = await _worker(session, user)
    agreement = await current_guarantee(session, worker, now=now)
    return OnboardingStatus(
        identity_verified=await _passed(session, user, "identity"),
        liveness_verified=await _passed(session, user, "liveness"),
        guarantor="none"
        if agreement is None
        else "active"
        if agreement.status is AgreementStatus.ACTIVE
        else "pending",
        invite=await _invite_view(session, agreement) if agreement else None,
    )


async def submit_identity(
    session: AsyncSession,
    user: User,
    submission: IdentitySubmission,
    *,
    provider: IdentityProvider | None = None,
    document: tuple[str, bytes] | None = None,
    document_store: DocumentStore | None = None,
) -> IdentityVerification:
    """Check the worker's identity details and keep only the provider's answer.

    A pass also puts the worker's name, phone and address on their account:
    Payscrow needs the phone when they create a job.
    """

    worker = await _worker(session, user)

    document_reference: str | None = None
    if document is not None:
        filename, content = document
        # Resolved at call time so tests can swap the bucket out.
        stored = await (document_store or document_store_module.default_document_store).store(
            filename=filename, content=content, prefix=f"worker-documents/{worker.id}"
        )
        document_reference = stored.reference or None
        submission = replace(submission, document_filename=filename, document_size=stored.size)

    result = await (provider or default_provider).verify(submission)
    record = IdentityVerification(
        user_id=user.id,
        provider=result.provider,
        provider_reference=result.reference,
        status=result.status,
        check_type="identity",
        document_reference=document_reference,
    )
    session.add(record)
    if not result.verified:
        raise CheckFailedError("We could not verify those identity details. Check them and try again.")

    user.display_name = f"{submission.first_name} {submission.last_name}".strip()
    user.phone = submission.phone
    user.address = submission.address
    await session.flush()
    return record


async def complete_liveness(
    session: AsyncSession,
    user: User,
    submission: LivenessSubmission,
    *,
    provider: LivenessProvider | None = None,
) -> IdentityVerification:
    """Run the selfie past the provider once the identity details have passed."""

    await _worker(session, user)
    if not await _passed(session, user, "identity"):
        raise StepOutOfOrderError("Verify your identity details before the liveness check.")

    result = await (provider or default_liveness_provider).check(submission)
    record = IdentityVerification(
        user_id=user.id,
        provider=result.provider,
        provider_reference=result.reference,
        status=result.status,
        check_type="liveness",
    )
    session.add(record)
    if not result.verified:
        raise CheckFailedError("We could not confirm a live capture. Try again in better lighting.")
    await session.flush()
    return record


async def invite_guarantor(
    session: AsyncSession,
    user: User,
    *,
    first_name: str,
    last_name: str,
    relationship: str,
    now: datetime | None = None,
) -> GuarantorInvite:
    """An invite link for the worker's guarantor, once both checks have passed."""

    worker = await _worker(session, user)
    if not (await _passed(session, user, "identity") and await _passed(session, user, "liveness")):
        raise StepOutOfOrderError("Finish verifying your identity before adding a guarantor.")
    if await has_active_guarantor(session, worker, now=now):
        raise StepOutOfOrderError("You already have an active guarantor.")

    agreement = await guarantor_service.invite_guarantor(
        session,
        worker,
        first_name=first_name,
        last_name=last_name,
        relationship=relationship,
        now=now,
    )
    return await _invite_view(session, agreement)
