"""Purpose: Assemble the guarantor dashboard from stored rows.

Dependencies: SQLAlchemy async sessions and app.models.domain.
Used by: the /me endpoints behind the guarantor dashboard.

Everything here is scoped to one guarantor: a guarantor only ever sees the
instruments they personally stand behind.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.domain import (
    AgreementStatus,
    AuditEvent,
    GuarantorAgreement,
    Job,
    User,
    Worker,
)
from app.services.guarantor import instrument_reference, status_label

#: How close to expiry counts as "expires soon" in the alerts list.
EXPIRING_WINDOW = timedelta(days=14)

#: Instrument states that end a guarantee other than by running out its year.
#: Triggered is absent on purpose: a called-in guarantee is a live obligation
#: for the guarantor, not a finished one, so it belongs with the active ones.
CLOSED_STATUSES = {
    AgreementStatus.PAID,
    AgreementStatus.DISMISSED,
    AgreementStatus.REVOKED,
    AgreementStatus.DECLINED,
}

#: A claim is running against these, so they still need the guarantor.
LIVE_STATUSES = {
    AgreementStatus.ACTIVE,
    AgreementStatus.TRIGGERED,
    AgreementStatus.DISPUTED,
    AgreementStatus.SUSPENDED,
}

#: Sent to the guarantor and waiting for their answer. Drafts are absent: the
#: platform has not sent them yet, so the guarantor has nothing to answer.
AWAITING_ANSWER_STATUSES = {AgreementStatus.PENDING_SIGNATURE}

#: Audit actions worth showing a guarantor, and how to word them.
ACTIVITY_LABELS = {
    "guarantor.created": "Guarantee requested",
    "guarantor.sent_for_signature": "Sent for signature",
    "guarantor.signed": "Terms accepted",
    "guarantor.declined": "Guarantee declined",
    "guarantor.identity_submitted": "Identity details submitted",
    "guarantor.identity_verified": "Identity verified",
    "guarantor.activated": "Guarantee activated",
    "guarantor.triggered": "Guarantee triggered",
    "guarantor.claim_disputed": "Claim disputed",
    "guarantor.claim_paid": "Claim paid",
    "guarantor.claim_dismissed": "Claim dismissed",
    "guarantor.revoked": "Guarantee revoked",
    "guarantor.expired": "Guarantee expired",
}


@dataclass(frozen=True)
class DashboardGuarantee:
    instrument_id: UUID
    reference: str
    worker_name: str
    worker_role: str | None
    avatar_url: str | None
    #: The linked job, when the request came with one. The guarantee itself
    #: covers the worker for the year, not just this job.
    job_title: str | None
    status: str
    #: Where "My guarantees" files it: "active", "expired" or "closed" once it
    #: has gone live, or "request" if it never did (it is then only on the
    #: requests screen).
    bucket: str
    #: Where "Guarantee requests" files it: "pending", "accepted" or
    #: "declined", or None for drafts and requests that lapsed unanswered.
    request_bucket: str | None
    requested_at: datetime
    #: When the guarantor accepted or declined.
    responded_at: datetime | None
    #: When the year began: the day both identity checks passed.
    started_on: datetime | None
    #: For a request, the deadline to answer; for a guarantee, the end of its year.
    valid_until: datetime
    #: When the guarantee stopped, for expired and closed ones.
    ended_on: datetime | None


@dataclass(frozen=True)
class ActivityEntry:
    id: UUID
    label: str
    at: datetime
    #: Whose guarantee it was, so the home screen can say "… - Jane A".
    worker_name: str = ""


@dataclass(frozen=True)
class GuaranteeDetail:
    card: DashboardGuarantee
    relationship: str
    scope: str
    conditions: str
    guarantor_name: str
    signed_at: datetime | None
    #: This guarantee's own history, newest first.
    activity: list["ActivityEntry"]
    #: The agreement, one paragraph per entry, as shown and downloaded.
    agreement: list[str]


@dataclass(frozen=True)
class DashboardSummary:
    active_count: int
    #: Requests waiting for this guarantor's answer.
    pending_count: int
    expired_count: int
    guarantees: list[DashboardGuarantee]
    recent_activity: list[ActivityEntry]
    #: The request awaiting this guarantor's decision, if any.
    action_required: DashboardGuarantee | None


def _as_aware(moment: datetime) -> datetime:
    """Treat naive timestamps as UTC.

    SQLite hands back naive datetimes where Postgres returns aware ones, so
    every stored timestamp is normalised before it is compared or sorted.
    """

    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)


def _bucket(agreement: GuarantorAgreement) -> str:
    """Group a guarantee for the All / Active / Expired tabs.

    Only instruments that went live are guarantees; the rest are requests. A
    guarantee covers the worker for a year, whatever jobs they take in it, so
    only the instrument's own state matters. A running claim stays active
    until it is paid or dismissed.
    """

    if agreement.verified_at is None:
        return "request"
    if agreement.status is AgreementStatus.EXPIRED:
        return "expired"
    if agreement.status in LIVE_STATUSES:
        return "active"
    return "closed"


def _request_bucket(agreement: GuarantorAgreement) -> str | None:
    """Group a request for the Pending / Accepted / Declined tabs.

    Accepted means the guarantor said yes, whatever has happened to the
    guarantee since; the year it then runs is on "My guarantees".
    """

    if agreement.status in AWAITING_ANSWER_STATUSES:
        return "pending"
    if agreement.status is AgreementStatus.DECLINED:
        return "declined"
    if agreement.signed_at is not None:
        return "accepted"
    return None


async def _build_card(session: AsyncSession, agreement: GuarantorAgreement) -> DashboardGuarantee:
    worker = await session.get(Worker, agreement.worker_id)
    person = await session.get(User, worker.user_id) if worker else None
    job = await session.get(Job, agreement.job_id) if agreement.job_id else None
    request_bucket = _request_bucket(agreement)

    return DashboardGuarantee(
        instrument_id=agreement.id,
        reference=instrument_reference(agreement.id),
        worker_name=person.display_name if person else "Unknown worker",
        worker_role=worker.role if worker else None,
        avatar_url=worker.avatar_url if worker else None,
        job_title=job.title if job else None,
        status=status_label(agreement.status),
        bucket=_bucket(agreement),
        request_bucket=request_bucket,
        requested_at=agreement.created_at,
        responded_at=(
            agreement.closed_at if request_bucket == "declined" else agreement.signed_at
        ),
        started_on=agreement.verified_at,
        valid_until=agreement.valid_until,
        ended_on=agreement.closed_at,
    )


async def _load_guarantees(
    session: AsyncSession, guarantor_user_id: UUID
) -> list[tuple[GuarantorAgreement, DashboardGuarantee]]:
    agreements = (
        await session.scalars(
            select(GuarantorAgreement)
            .where(GuarantorAgreement.guarantor_user_id == guarantor_user_id)
            .order_by(GuarantorAgreement.created_at.desc())
            .options(selectinload(GuarantorAgreement.signatures))
        )
    ).all()

    return [(agreement, await _build_card(session, agreement)) for agreement in agreements]


async def _activity(
    session: AsyncSession,
    instrument_ids: list[UUID],
    *,
    limit: int | None = None,
    worker_names: dict[UUID, str] | None = None,
) -> list[ActivityEntry]:
    if not instrument_ids:
        return []
    names = worker_names or {}

    query = (
        select(AuditEvent)
        .where(
            AuditEvent.entity_type == "guarantor_agreement",
            AuditEvent.entity_id.in_(instrument_ids),
            AuditEvent.action.in_(tuple(ACTIVITY_LABELS)),
        )
        .order_by(AuditEvent.created_at.desc())
    )
    if limit is not None:
        query = query.limit(limit)

    return [
        ActivityEntry(
            id=event.id,
            label=ACTIVITY_LABELS.get(event.action, event.action),
            at=event.created_at,
            worker_name=names.get(event.entity_id, ""),
        )
        for event in (await session.scalars(query)).all()
    ]


async def load_summary(session: AsyncSession, guarantor_user_id: UUID) -> DashboardSummary:
    """Everything the home screen shows, for one guarantor."""

    cards = await _load_guarantees(session, guarantor_user_id)

    active = [card for _, card in cards if card.bucket == "active"]
    expired = [card for _, card in cards if card.bucket == "expired"]
    pending = [card for _, card in cards if card.request_bucket == "pending"]

    # Newest first, so the banner names the latest request.
    waiting = next((card for _, card in cards if card.request_bucket == "pending"), None)

    activity = await _activity(
        session,
        [agreement.id for agreement, _ in cards],
        limit=10,
        worker_names={card.instrument_id: card.worker_name for _, card in cards},
    )

    return DashboardSummary(
        active_count=len(active),
        pending_count=len(pending),
        expired_count=len(expired),
        guarantees=[card for _, card in cards],
        recent_activity=activity,
        action_required=waiting,
    )


def _long_date(moment: datetime) -> str:
    return f"{moment.day} {moment:%B, %Y}"


def agreement_paragraphs(
    agreement: GuarantorAgreement, *, worker_name: str, guarantor_name: str
) -> list[str]:
    """The agreement the guarantor accepted, built from what was stored.

    Plain wording over the stored scope and conditions; the designs only carry
    placeholder text for this page, so legal wording can replace it here
    without touching the screens.
    """

    if agreement.verified_at is not None:
        start = _as_aware(agreement.verified_at)
        term = (
            f"The guarantee runs for one year, from {_long_date(start)} "
            f"to {_long_date(_as_aware(agreement.valid_until))}."
        )
    else:
        term = (
            "The guarantee runs for one year from the day the Guarantor's identity "
            "checks are completed."
        )

    paragraphs = [
        f'This agreement is between {guarantor_name} ("the Guarantor") and '
        f'{worker_name} ("the Worker"). The Guarantor vouches for the Worker '
        f"as their {agreement.relationship_type}, for all work the Worker takes "
        f"on during the term, not for a single job. {term}",
        f"Scope: {agreement.scope}",
        f"Conditions: {agreement.conditions}",
    ]
    if agreement.signed_at is not None:
        paragraphs.append(
            f"Accepted electronically by {guarantor_name} on "
            f"{_long_date(_as_aware(agreement.signed_at))}."
        )
    return paragraphs


class GuaranteeNotFoundError(Exception):
    """No guarantee with that id stands behind this guarantor's name."""


async def load_guarantee(
    session: AsyncSession, guarantor_user_id: UUID, instrument_id: UUID
) -> GuaranteeDetail:
    """One guarantee and its history, for the guarantee details screen.

    Someone else's guarantee is reported as missing rather than forbidden, so
    the response does not confirm that the id exists.
    """

    agreement = await session.get(GuarantorAgreement, instrument_id)
    if agreement is None or agreement.guarantor_user_id != guarantor_user_id:
        raise GuaranteeNotFoundError(f"No guarantee with id {instrument_id}.")

    guarantor = await session.get(User, agreement.guarantor_user_id)
    guarantor_name = guarantor.display_name if guarantor else ""
    card = await _build_card(session, agreement)
    return GuaranteeDetail(
        card=card,
        relationship=agreement.relationship_type,
        scope=agreement.scope,
        conditions=agreement.conditions,
        guarantor_name=guarantor_name,
        signed_at=agreement.signed_at,
        activity=await _activity(session, [agreement.id]),
        agreement=agreement_paragraphs(
            agreement, worker_name=card.worker_name, guarantor_name=guarantor_name
        ),
    )


@dataclass(frozen=True)
class Notification:
    id: str
    title: str
    body: str
    at: datetime
    icon: str


async def load_notifications(
    session: AsyncSession, guarantor_user_id: UUID, *, now: datetime | None = None
) -> list[Notification]:
    """Derive the alerts list from the audit trail and upcoming expiries.

    There is no notifications table yet; these are read off what actually
    happened, so nothing can drift out of step with the instruments.
    """

    moment = now or datetime.now(tz=UTC)
    cards = await _load_guarantees(session, guarantor_user_id)
    notifications: list[Notification] = []

    for agreement, card in cards:
        subject = card.worker_name

        if agreement.status is AgreementStatus.ACTIVE and agreement.verified_at:
            notifications.append(
                Notification(
                    id=f"{agreement.id}-activated",
                    title="Guarantee activated",
                    body=f"Your guarantee for {subject} is now active.",
                    at=_as_aware(agreement.verified_at),
                    icon="bell",
                )
            )
            notifications.append(
                Notification(
                    id=f"{agreement.id}-verified",
                    title="Identification verification completed",
                    body="Your identity checks passed.",
                    at=_as_aware(agreement.verified_at),
                    icon="check",
                )
            )

        valid_until = _as_aware(agreement.valid_until)

        if agreement.status is AgreementStatus.ACTIVE and moment <= valid_until <= moment + EXPIRING_WINDOW:
            notifications.append(
                Notification(
                    id=f"{agreement.id}-expiring",
                    title="Guarantee expires soon",
                    body=f"Your guarantee for {subject} ends on {valid_until:%d %b %Y}.",
                    at=valid_until,
                    icon="calendar",
                )
            )

    notifications.sort(key=lambda item: item.at, reverse=True)
    return notifications
