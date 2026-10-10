"""Purpose: Build the worker's and the customer's job notifications.

Dependencies: SQLAlchemy async sessions and app.models.domain.
Used by: the worker and customer notification screens.

Derived from each job's audit trail rather than stored separately, so the
list can never disagree with what happened. Who sees what follows the job
flow document: the worker hears about payments, completion and disputes; the
customer about completion and disputes. Emails carry the same news.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.domain import AuditEvent, Job

FEED_ACTIONS = (
    "escrow.funded",
    "job.completed",
    "escrow.released",
    "escrow.dispute_raised",
    "escrow.dispute_resolved",
)

OUTCOMES = {
    "Close": "Payment has been released",
    "Refund": "Payment was refunded to the customer",
    "Split": "Payment was split between both parties",
}


@dataclass(frozen=True)
class FeedItem:
    id: UUID
    job_id: UUID
    title: str
    body: str
    at: datetime
    #: "check" for progress, "warning" for disputes.
    icon: str


def _as_aware(moment: datetime) -> datetime:
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)


def _naira(job: Job) -> str:
    return f"₦{job.agreed_amount:,.0f}"


def _short(name: str | None, fallback: str) -> str:
    if not name:
        return fallback
    first, *rest = name.split()
    return f"{first} {rest[-1][0]}." if rest else first


def _item(event: AuditEvent, job: Job, audience: str, worker_name: str) -> FeedItem | None:
    job_title = job.title.lower()
    customer = _short(job.client_name, "Your customer")
    worker_first = worker_name.split()[0] if worker_name else "The worker"
    meta = event.event_metadata or {}

    match event.action, audience:
        case "escrow.funded", "worker":
            title = "Payment received"
            body = f"{customer} paid {_naira(job)} for {job_title}. It is held in escrow until the job is confirmed"
        case "job.completed", "worker":
            title = "Job completed"
            body = f"You marked {job_title} as done. Waiting for {customer} to release the payment"
        case "job.completed", "customer":
            title = "Job completed"
            body = f"{worker_first} marked {job_title} as done. Enter the job code to confirm and release payment"
        case "escrow.released", "worker":
            title = "Payment released"
            body = f"{_naira(job)} for {job_title} has been released to you"
        case "escrow.dispute_raised", _:
            title = "Dispute opened"
            body = f"A dispute was opened on {job.title}. Payment stays in escrow while it is reviewed"
        case "escrow.dispute_resolved", _:
            title = "Dispute closed"
            outcome = OUTCOMES.get(meta.get("resolution") or "", "Payscrow has ruled")
            body = f"A dispute was closed on {job.title}. {outcome}"
        case _:
            return None

    return FeedItem(
        id=event.id,
        job_id=job.id,
        title=title,
        body=body,
        at=_as_aware(event.created_at),
        icon="warning" if event.action.startswith("escrow.dispute") else "check",
    )


async def feed_for(
    session: AsyncSession, jobs: list[Job], *, audience: str, worker_name: str
) -> list[FeedItem]:
    """Newest first."""

    by_id = {job.id: job for job in jobs}
    if not by_id:
        return []
    events = (
        await session.scalars(
            select(AuditEvent)
            .where(
                AuditEvent.entity_type == "job",
                AuditEvent.entity_id.in_(tuple(by_id)),
                AuditEvent.action.in_(FEED_ACTIONS),
            )
            .order_by(AuditEvent.created_at.desc())
            .limit(100)
        )
    ).all()
    items = [_item(event, by_id[event.entity_id], audience, worker_name) for event in events]
    return [item for item in items if item is not None]
