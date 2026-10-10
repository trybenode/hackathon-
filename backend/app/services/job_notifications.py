"""Purpose: Email the worker and customer as a job's money moves.

Dependencies: app.services.email_sender and app.core.config.
Used by: app.services.escrow.

Who hears what (job flow document, "Notifications"):
  customer: the job was marked completed (with their job page link)
  worker:   the payment was received; the payment was released
  both:     a dispute opened (and the platform, if OPS_EMAIL is set)

Sending is best-effort: an email that fails is logged, never allowed to undo
or block a step in the money's journey.
"""

from __future__ import annotations

import logging

from app.core.config import get_settings
from app.models.domain import Job
from app.services import email_sender as email_sender_module
from app.services.email_sender import EmailMessage

logger = logging.getLogger(__name__)


def job_page_url(job: Job) -> str:
    """The customer's page for the job: the same link the worker shared."""

    return f"{get_settings().frontend_base_url.rstrip('/')}/j/{job.link_token}"


def worker_job_url(job: Job) -> str:
    return f"{get_settings().frontend_base_url.rstrip('/')}/worker/jobs/{job.id}"


def _naira(job: Job) -> str:
    return f"NGN {job.agreed_amount:,.2f}"


async def _send(to: str | None, subject: str, body: str) -> None:
    if not to:
        return
    try:
        # Resolved at call time so tests can swap the sender.
        await email_sender_module.default_email_sender.send(EmailMessage(to=to, subject=subject, body=body))
    except Exception:  # noqa: BLE001 - a notification must never break the flow
        logger.exception("Could not send %r to %s", subject, to)


async def job_completed(job: Job, worker_name: str, window_hours: int) -> None:
    await _send(
        job.client_email,
        f"{worker_name} has completed your {job.title.lower()} job",
        f"Hello {job.client_name or ''},\n\n"
        f"{worker_name} marked your {job.title.lower()} job as completed. Your payment of "
        f"{_naira(job)} is still held safely in escrow.\n\n"
        "If the work is done, open your job page, enter the escrow code Payscrow emailed "
        "you when you paid, and rate the job; that releases the payment. If something is "
        "wrong, report a problem from the same page.\n\n"
        f"You have {window_hours} hours. After that a dispute opens so the payment can be "
        "reviewed; it is never released without your code.\n\n"
        f"Your job page: {job_page_url(job)}\n",
    )


async def payment_received(job: Job, worker_email: str) -> None:
    await _send(
        worker_email,
        f"Payment received for {job.title.lower()}",
        f"{job.client_name or 'Your customer'} paid {_naira(job)} into escrow for "
        f"{job.title.lower()}. The money is held safely until the job is confirmed, so "
        "you can start.\n\n"
        f"Job details: {worker_job_url(job)}\n",
    )


async def payment_released(job: Job, worker_email: str) -> None:
    await _send(
        worker_email,
        f"Payment released for {job.title.lower()}",
        f"{job.client_name or 'Your customer'} confirmed the job and released "
        f"{_naira(job)} to you. Payscrow pays it out to your settlement account.\n\n"
        f"Job details: {worker_job_url(job)}\n",
    )


async def dispute_opened(job: Job, worker_email: str, raised_by: str, reason: str) -> None:
    who = {
        "customer": "the customer",
        "worker": "the worker",
        "timeout": "the platform, because the customer did not confirm in time",
    }.get(raised_by, raised_by)
    subject = f"Dispute opened on {job.title.lower()}"
    body = (
        f"A dispute was opened by {who} on {job.title.lower()} ({_naira(job)}).\n\n"
        f"Reason: {reason}\n\n"
        "The payment stays held in escrow while Payscrow reviews it. You can follow each "
        "stage (negotiation, evidence, decision) on the job page.\n\n"
    )
    await _send(job.client_email, subject, body + f"Your job page: {job_page_url(job)}\n")
    await _send(worker_email, subject, body + f"Job details: {worker_job_url(job)}\n")
    await _send(get_settings().ops_email or None, subject, body + f"Job: {job.id}\n")
