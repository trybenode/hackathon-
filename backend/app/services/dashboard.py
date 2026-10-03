"""Purpose: Assemble the guarantor dashboard from stored rows.

Dependencies: SQLAlchemy async sessions and app.models.domain.
Used by: the /me endpoints behind the guarantor dashboard.

Everything here is scoped to one guarantor: a guarantor only ever sees the
instruments they personally stand behind.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.domain import (
    AgreementStatus,
    AuditEvent,
    GuarantorAgreement,
    Job,
    JobStatus,
    User,
    Worker,
)
from app.services.guarantor import status_label

#: A guarantee whose job has finished reads as "Completed" on the dashboard,
#: even though the instrument itself is still within its validity window.
FINISHED_JOB_STATUSES = {JobStatus.COMPLETED, JobStatus.RELEASED}

#: How close to expiry counts as "expires soon" in the alerts list.
EXPIRING_WINDOW = timedelta(days=14)

#: Instrument states that mean the guarantee is over. Triggered is absent on
#: purpose: a called-in guarantee is a live obligation for the guarantor, not
#: a finished one, so it belongs with the active guarantees.
CLOSED_STATUSES = {
    AgreementStatus.PAID,
    AgreementStatus.DISMISSED,
    AgreementStatus.REVOKED,
    AgreementStatus.EXPIRED,
    AgreementStatus.DECLINED,
}

#: A claim is running against these, so they still need the guarantor.
LIVE_STATUSES = {
    AgreementStatus.ACTIVE,
    AgreementStatus.TRIGGERED,
    AgreementStatus.DISPUTED,
    AgreementStatus.SUSPENDED,
}

#: Waiting on the guarantor, so not yet a live guarantee.
PENDING_STATUSES = {
    AgreementStatus.DRAFT,
    AgreementStatus.REQUESTED,
    AgreementStatus.PENDING_SIGNATURE,
    AgreementStatus.PENDING_VERIFICATION,
}

#: Audit actions worth showing a guarantor, and how to word them.
ACTIVITY_LABELS = {
    "guarantor.created": "Guarantee requested",
    "guarantor.sent_for_signature": "Sent for signature",
    "guarantor.signed": "Terms accepted",
    "guarantor.declined": "Guarantee declined",
    "guarantor.identity_submitted": "Identity details submitted",
    "guarantor.identity_verified": "Identity verified",
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
    worker_name: str
    worker_role: str | None
    avatar_url: str | None
    job_title: str | None
    amount: Decimal | None
    status: str
    #: Which tab shows this card: "pending", "active" or "completed".
    bucket: str
    started_on: datetime | None


@dataclass(frozen=True)
class ActivityEntry:
    id: UUID
    label: str
    at: datetime


@dataclass(frozen=True)
class DashboardSummary:
    active_count: int
    completed_count: int
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


def _card_status(agreement: GuarantorAgreement, job: Job | None) -> str:
    if job is not None and job.status in FINISHED_JOB_STATUSES:
        return "Completed"
    return status_label(agreement.status)


def _bucket(agreement: GuarantorAgreement, job: Job | None) -> str:
    """Group a guarantee for the All / Active / Completed tabs.

    A guarantee is done when its job finished, or when the instrument closed
    for any reason, so a triggered or revoked guarantee is filed with the
    completed ones rather than vanishing from both tabs.
    """

    if agreement.status in PENDING_STATUSES:
        return "pending"
    if agreement.status in CLOSED_STATUSES:
        return "completed"
    # A running claim stays active even if the job itself finished: the claim
    # outlives the work.
    if agreement.status in {AgreementStatus.TRIGGERED, AgreementStatus.DISPUTED}:
        return "active"
    if job is not None and job.status in FINISHED_JOB_STATUSES:
        return "completed"
    return "active" if agreement.status in LIVE_STATUSES else "completed"


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

    cards: list[tuple[GuarantorAgreement, DashboardGuarantee]] = []
    for agreement in agreements:
        worker = await session.get(Worker, agreement.worker_id)
        person = await session.get(User, worker.user_id) if worker else None
        job = await session.get(Job, agreement.job_id) if agreement.job_id else None

        cards.append(
            (
                agreement,
                DashboardGuarantee(
                    instrument_id=agreement.id,
                    worker_name=person.display_name if person else "Unknown worker",
                    worker_role=worker.role if worker else None,
                    avatar_url=worker.avatar_url if worker else None,
                    job_title=job.title if job else None,
                    amount=job.agreed_amount if job else None,
                    status=_card_status(agreement, job),
                    bucket=_bucket(agreement, job),
                    started_on=agreement.signed_at or agreement.created_at,
                ),
            )
        )

    return cards


async def load_summary(session: AsyncSession, guarantor_user_id: UUID) -> DashboardSummary:
    """Everything the home screen shows, for one guarantor."""

    cards = await _load_guarantees(session, guarantor_user_id)

    active = [card for _, card in cards if card.bucket == "active"]
    completed = [card for _, card in cards if card.bucket == "completed"]

    waiting = next(
        (
            card
            for agreement, card in cards
            if agreement.status
            in {AgreementStatus.PENDING_SIGNATURE, AgreementStatus.PENDING_VERIFICATION}
        ),
        None,
    )

    instrument_ids = [agreement.id for agreement, _ in cards]
    activity: list[ActivityEntry] = []
    if instrument_ids:
        events = (
            await session.scalars(
                select(AuditEvent)
                .where(
                    AuditEvent.entity_type == "guarantor_agreement",
                    AuditEvent.entity_id.in_(instrument_ids),
                    AuditEvent.action.in_(tuple(ACTIVITY_LABELS)),
                )
                .order_by(AuditEvent.created_at.desc())
                .limit(10)
            )
        ).all()
        activity = [
            ActivityEntry(
                id=event.id,
                label=ACTIVITY_LABELS.get(event.action, event.action),
                at=event.created_at,
            )
            for event in events
        ]

    return DashboardSummary(
        active_count=len(active),
        completed_count=len(completed),
        guarantees=[card for _, card in cards],
        recent_activity=activity,
        action_required=waiting,
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
        subject = card.job_title or card.worker_name

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
