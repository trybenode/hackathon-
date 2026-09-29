"""Purpose: Own the guarantor instrument lifecycle, signatures, and audit trail.

Dependencies: SQLAlchemy async sessions, app.models.domain, and app.schemas.api.
Used by: the guarantor API endpoints.

Lifecycle
---------
    Draft ──send──▶ Pending Signature ──sign(accepted)──▶ Active
      │                    │                                 │
      │                    ├──sign(declined)──▶ Declined      ├──trigger──▶ Triggered
      │                    ├──expire──────────▶ Expired       ├──expire───▶ Expired
      └──revoke───────────┴──revoke──────────▶ Revoked  ◀────┘ (revoke)

Triggered, Expired, Revoked, and Declined are terminal: nothing moves out of
them. Suspended is an administrative hold on an Active instrument and can only
return to Active or close out.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.domain import (
    AgreementStatus,
    AuditEvent,
    ElectronicSignature,
    GuarantorAgreement,
    User,
    Worker,
)
from app.schemas.api import GuarantorInstrumentCreateRequest, GuarantorSignRequest

ALLOWED_TRANSITIONS: dict[AgreementStatus, frozenset[AgreementStatus]] = {
    AgreementStatus.DRAFT: frozenset(
        {AgreementStatus.PENDING_SIGNATURE, AgreementStatus.REVOKED}
    ),
    # Legacy state from the first schema pass; treated as a draft.
    AgreementStatus.REQUESTED: frozenset(
        {AgreementStatus.PENDING_SIGNATURE, AgreementStatus.REVOKED}
    ),
    AgreementStatus.PENDING_SIGNATURE: frozenset(
        {
            AgreementStatus.ACTIVE,
            AgreementStatus.DECLINED,
            AgreementStatus.EXPIRED,
            AgreementStatus.REVOKED,
        }
    ),
    AgreementStatus.ACTIVE: frozenset(
        {
            AgreementStatus.TRIGGERED,
            AgreementStatus.EXPIRED,
            AgreementStatus.REVOKED,
            AgreementStatus.SUSPENDED,
        }
    ),
    AgreementStatus.SUSPENDED: frozenset(
        {AgreementStatus.ACTIVE, AgreementStatus.REVOKED, AgreementStatus.EXPIRED}
    ),
    AgreementStatus.TRIGGERED: frozenset(),
    AgreementStatus.EXPIRED: frozenset(),
    AgreementStatus.REVOKED: frozenset(),
    AgreementStatus.DECLINED: frozenset(),
}

TERMINAL_STATUSES = frozenset(
    {
        AgreementStatus.TRIGGERED,
        AgreementStatus.EXPIRED,
        AgreementStatus.REVOKED,
        AgreementStatus.DECLINED,
    }
)

#: Statuses an unsigned or live instrument can sit in while the clock runs.
EXPIRABLE_STATUSES = frozenset(
    {
        AgreementStatus.DRAFT,
        AgreementStatus.REQUESTED,
        AgreementStatus.PENDING_SIGNATURE,
        AgreementStatus.ACTIVE,
        AgreementStatus.SUSPENDED,
    }
)

#: Internal status -> the label the API and UI show.
STATUS_LABELS: dict[AgreementStatus, str] = {
    AgreementStatus.DRAFT: "Draft",
    AgreementStatus.REQUESTED: "Draft",
    AgreementStatus.PENDING_SIGNATURE: "Pending Signature",
    AgreementStatus.ACTIVE: "Active",
    AgreementStatus.TRIGGERED: "Triggered",
    AgreementStatus.SUSPENDED: "Suspended",
    AgreementStatus.REVOKED: "Revoked",
    AgreementStatus.EXPIRED: "Expired",
    AgreementStatus.DECLINED: "Declined",
}


class GuarantorError(Exception):
    """Base class for guarantor lifecycle failures."""


class InstrumentNotFoundError(GuarantorError):
    """No guarantor instrument exists for the given id."""


class WorkerNotFoundError(GuarantorError):
    """The instrument references a worker that does not exist."""


class SelfGuaranteeError(GuarantorError):
    """A worker cannot act as their own guarantor."""


class ValidityWindowError(GuarantorError):
    """valid_until must be in the future when the instrument is created."""


class InvalidTransitionError(GuarantorError):
    """The requested lifecycle move is not allowed from the current status."""

    def __init__(self, current: AgreementStatus, target: AgreementStatus) -> None:
        super().__init__(
            f"Cannot move a guarantor instrument from {STATUS_LABELS[current]} "
            f"to {STATUS_LABELS[target]}."
        )
        self.current = current
        self.target = target


def status_label(status: AgreementStatus) -> str:
    """Return the display label for an internal status value."""

    return STATUS_LABELS[status]


def build_signature_hash(
    *,
    agreement_id: UUID,
    signer_name: str,
    signer_phone: str,
    accepted: bool,
    signed_at: datetime,
    ip_address: str,
    user_agent: str,
) -> str:
    """Hash the signature evidence so later tampering is detectable.

    The hash covers everything the signer agreed to and the context it was
    captured in, so a stored signature row can be re-derived and compared.
    """

    payload = "|".join(
        [
            str(agreement_id),
            signer_name.strip().casefold(),
            signer_phone.strip(),
            "accepted" if accepted else "declined",
            signed_at.astimezone(UTC).isoformat(),
            ip_address.strip(),
            user_agent.strip(),
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _now() -> datetime:
    return datetime.now(tz=UTC)


def _as_aware(moment: datetime) -> datetime:
    """Treat naive timestamps as UTC so comparisons never raise."""

    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)


def _record_audit(
    session: AsyncSession,
    *,
    agreement: GuarantorAgreement,
    action: str,
    actor_id: UUID | None = None,
    metadata: dict | None = None,
) -> None:
    session.add(
        AuditEvent(
            actor_id=actor_id,
            entity_type="guarantor_agreement",
            entity_id=agreement.id,
            action=action,
            event_metadata=metadata or {},
        )
    )


def apply_transition(
    agreement: GuarantorAgreement,
    target: AgreementStatus,
    *,
    reason: str | None = None,
    at: datetime | None = None,
) -> GuarantorAgreement:
    """Move an instrument to `target`, refusing moves the lifecycle forbids.

    Stamps the timestamp that belongs to the target state so the history of an
    instrument can be read off the row itself.
    """

    current = agreement.status
    if target not in ALLOWED_TRANSITIONS[current]:
        raise InvalidTransitionError(current, target)

    moment = at or _now()
    agreement.status = target
    if reason is not None:
        agreement.status_reason = reason

    if target is AgreementStatus.ACTIVE and agreement.signed_at is None:
        agreement.signed_at = moment
    elif target is AgreementStatus.TRIGGERED:
        agreement.triggered_at = moment

    if target in TERMINAL_STATUSES:
        agreement.closed_at = moment

    return agreement


async def _get_agreement(session: AsyncSession, instrument_id: UUID) -> GuarantorAgreement:
    agreement = await session.get(GuarantorAgreement, instrument_id)
    if agreement is None:
        raise InstrumentNotFoundError(f"No guarantor instrument with id {instrument_id}.")
    return agreement


async def _resolve_guarantor_user(
    session: AsyncSession, *, email: str, full_name: str
) -> User:
    """Find the guarantor's user record by email, creating it when new.

    A guarantor is always a real person, so the instrument points at a `users`
    row rather than storing a loose name.
    """

    normalised = email.strip().casefold()
    existing = await session.scalar(select(User).where(User.email == normalised))
    if existing is not None:
        return existing

    user = User(email=normalised, display_name=full_name.strip())
    session.add(user)
    await session.flush()
    return user


async def create_instrument(
    session: AsyncSession,
    request: GuarantorInstrumentCreateRequest,
    *,
    as_draft: bool = False,
    now: datetime | None = None,
) -> GuarantorAgreement:
    """Create a guarantor instrument for a worker.

    Starts in Draft when `as_draft` is set, otherwise goes straight out for
    signature. Creates the guarantor's user record if this is their first
    instrument.
    """

    moment = now or _now()
    worker = await session.get(Worker, request.worker_id)
    if worker is None:
        raise WorkerNotFoundError(f"No worker with id {request.worker_id}.")

    if _as_aware(request.valid_until) <= moment:
        raise ValidityWindowError("valid_until must be in the future.")

    guarantor = await _resolve_guarantor_user(
        session, email=request.guarantor.email, full_name=request.guarantor.full_name
    )
    if guarantor.id == worker.user_id:
        raise SelfGuaranteeError("A worker cannot act as their own guarantor.")

    agreement = GuarantorAgreement(
        worker_id=worker.id,
        guarantor_user_id=guarantor.id,
        job_id=request.job_id,
        scope=request.scope,
        conditions=request.conditions,
        relationship_type=request.guarantor.relationship,
        guarantor_phone=request.guarantor.phone,
        guarantor_address=request.guarantor.address,
        status=AgreementStatus.DRAFT if as_draft else AgreementStatus.PENDING_SIGNATURE,
        valid_until=request.valid_until,
    )
    session.add(agreement)
    await session.flush()

    _record_audit(
        session,
        agreement=agreement,
        action="guarantor.created",
        metadata={"status": status_label(agreement.status)},
    )
    return agreement


async def send_for_signature(
    session: AsyncSession, instrument_id: UUID, *, now: datetime | None = None
) -> GuarantorAgreement:
    """Move a draft instrument out for the guarantor's signature."""

    agreement = await _get_agreement(session, instrument_id)
    apply_transition(agreement, AgreementStatus.PENDING_SIGNATURE, at=now)
    _record_audit(session, agreement=agreement, action="guarantor.sent_for_signature")
    return agreement


async def sign_instrument(
    session: AsyncSession,
    instrument_id: UUID,
    request: GuarantorSignRequest,
    *,
    now: datetime | None = None,
) -> GuarantorAgreement:
    """Record the guarantor's decision and activate or decline the instrument.

    Signing after `valid_until` expires the instrument instead of activating
    it, so a stale signing link cannot bring a dead guarantee to life.
    """

    moment = now or _now()
    agreement = await _get_agreement(session, instrument_id)

    if (
        agreement.status in EXPIRABLE_STATUSES
        and _as_aware(agreement.valid_until) <= moment
    ):
        apply_transition(
            agreement,
            AgreementStatus.EXPIRED,
            reason="Validity period ended before signature.",
            at=moment,
        )
        _record_audit(session, agreement=agreement, action="guarantor.expired")
        raise InvalidTransitionError(AgreementStatus.EXPIRED, AgreementStatus.ACTIVE)

    target = AgreementStatus.ACTIVE if request.accepted else AgreementStatus.DECLINED
    signed_at = _as_aware(request.signature_metadata.timestamp)

    apply_transition(agreement, target, at=signed_at)
    session.add(
        ElectronicSignature(
            agreement_id=agreement.id,
            signer_id=agreement.guarantor_user_id,
            signer_name=request.signer_name,
            signer_phone=request.signer_phone,
            accepted=request.accepted,
            ip_address=request.signature_metadata.ip,
            user_agent=request.signature_metadata.user_agent,
            signed_at=signed_at,
            signature_hash=build_signature_hash(
                agreement_id=agreement.id,
                signer_name=request.signer_name,
                signer_phone=request.signer_phone,
                accepted=request.accepted,
                signed_at=signed_at,
                ip_address=request.signature_metadata.ip,
                user_agent=request.signature_metadata.user_agent,
            ),
        )
    )
    _record_audit(
        session,
        agreement=agreement,
        action="guarantor.signed" if request.accepted else "guarantor.declined",
        actor_id=agreement.guarantor_user_id,
        metadata={"accepted": request.accepted},
    )
    return agreement


async def trigger_instrument(
    session: AsyncSession,
    instrument_id: UUID,
    *,
    reason: str,
    now: datetime | None = None,
) -> GuarantorAgreement:
    """Invoke an active guarantee, e.g. after a failed or disputed job."""

    agreement = await _get_agreement(session, instrument_id)
    apply_transition(agreement, AgreementStatus.TRIGGERED, reason=reason, at=now)
    _record_audit(
        session,
        agreement=agreement,
        action="guarantor.triggered",
        metadata={"reason": reason},
    )
    return agreement


async def revoke_instrument(
    session: AsyncSession,
    instrument_id: UUID,
    *,
    reason: str,
    now: datetime | None = None,
) -> GuarantorAgreement:
    """Withdraw an instrument before it runs its course."""

    agreement = await _get_agreement(session, instrument_id)
    apply_transition(agreement, AgreementStatus.REVOKED, reason=reason, at=now)
    _record_audit(
        session,
        agreement=agreement,
        action="guarantor.revoked",
        metadata={"reason": reason},
    )
    return agreement


async def expire_due_instruments(
    session: AsyncSession, *, now: datetime | None = None
) -> list[GuarantorAgreement]:
    """Expire every instrument whose validity period has ended.

    Called by a sweep rather than a request, so it never raises: instruments in
    a terminal state are simply skipped.
    """

    moment = now or _now()
    due = await session.scalars(
        select(GuarantorAgreement).where(
            GuarantorAgreement.status.in_(tuple(EXPIRABLE_STATUSES)),
            GuarantorAgreement.valid_until <= moment,
        )
    )

    expired: list[GuarantorAgreement] = []
    for agreement in due:
        apply_transition(
            agreement,
            AgreementStatus.EXPIRED,
            reason="Validity period ended.",
            at=moment,
        )
        _record_audit(session, agreement=agreement, action="guarantor.expired")
        expired.append(agreement)
    return expired


async def get_instrument(session: AsyncSession, instrument_id: UUID) -> GuarantorAgreement:
    """Load one instrument or raise `InstrumentNotFoundError`."""

    return await _get_agreement(session, instrument_id)


async def list_instruments(
    session: AsyncSession,
    *,
    worker_id: UUID | None = None,
    statuses: Sequence[AgreementStatus] | None = None,
) -> Sequence[GuarantorAgreement]:
    """List instruments, newest first, optionally filtered by worker/status."""

    query = select(GuarantorAgreement).order_by(GuarantorAgreement.created_at.desc())
    if worker_id is not None:
        query = query.where(GuarantorAgreement.worker_id == worker_id)
    if statuses:
        query = query.where(GuarantorAgreement.status.in_(tuple(statuses)))

    return (await session.scalars(query)).all()
