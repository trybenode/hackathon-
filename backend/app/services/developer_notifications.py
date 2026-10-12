"""Purpose: Email developers about their verification, and operators about requests.

Dependencies: app.core.config, app.services.email_sender, app.services.email_templates.
Used by: scripts/review_developer.py after a decision is committed, and the
attest-request endpoint.

Best-effort: a lost email is logged, never allowed to undo a decision.
"""

from __future__ import annotations

import html
import logging

from app.core.config import get_settings
from app.services import email_sender as email_sender_module
from app.services.email_sender import EmailDeliveryError, EmailMessage
from app.services.email_templates import BACKGROUND, FONT_STACK, GREY_600, PRIMARY

logger = logging.getLogger(__name__)


def _html(title: str, lines: list[str], link: tuple[str, str] | None) -> str:
    paragraphs = "".join(
        f'<p style="margin:0 0 12px;color:#212121;font-size:15px;line-height:22px">{html.escape(line)}</p>'
        for line in lines
    )
    button = (
        f'<p style="margin:20px 0 0"><a href="{html.escape(link[1])}" style="display:inline-block;'
        f"background:{PRIMARY};color:#ffffff;text-decoration:none;padding:12px 20px;border-radius:10px;"
        f'font-weight:600;font-size:15px">{html.escape(link[0])}</a></p>'
        if link
        else ""
    )
    return (
        f'<div style="background:{BACKGROUND};padding:32px 16px;font-family:{FONT_STACK}">'
        '<div style="max-width:480px;margin:0 auto;background:#ffffff;border-radius:16px;padding:28px">'
        f'<h1 style="margin:0 0 16px;font-size:20px;color:#212121">{html.escape(title)}</h1>'
        f"{paragraphs}{button}"
        f'<p style="margin:24px 0 0;color:{GREY_600};font-size:12px">You are receiving this because you have a developer account.</p>'
        "</div></div>"
    )


async def _send(to: str, subject: str, title: str, lines: list[str], link: tuple[str, str] | None = None) -> None:
    text = "\n\n".join([title, *lines, *( [f"{link[0]}: {link[1]}"] if link else [])])
    try:
        # Resolved at call time so tests can swap the sender out.
        await email_sender_module.default_email_sender.send(
            EmailMessage(to=to, subject=subject, body=text, html=_html(title, lines, link))
        )
    except EmailDeliveryError:
        logger.warning("Could not send %r to %s", subject, to, exc_info=True)


def _url(path: str) -> str:
    return f"{get_settings().frontend_base_url.rstrip('/')}{path}"


async def kyb_approved(to: str, business_name: str) -> None:
    await _send(
        to,
        "Your business is verified",
        "Your business is verified",
        [
            f"{business_name} passed our identity and business review.",
            "API access is unlocked: create a Sandbox key to try the API against our demo workers, "
            "then a Production key when you are ready.",
        ],
        ("Create an API key", _url("/developer/keys")),
    )


async def kyb_rejected(to: str, note: str) -> None:
    await _send(
        to,
        "We could not verify your business yet",
        "We could not verify your business yet",
        [
            f"What to fix: {note}",
            "Update your details and documents, then submit them again.",
        ],
        ("Update verification", _url("/developer/verify")),
    )


async def attest_requested(business_name: str, key_name: str, key_id: str) -> None:
    """Tell operators a platform wants its imported records to count as verified."""

    to = get_settings().ops_email.strip()
    if not to:
        return
    await _send(
        to,
        f"Attest request: {business_name}",
        "A platform asked to attest its records",
        [
            f"{business_name} asked for {key_name} ({key_id}) to attest the records it imports.",
            f"Review it with: python scripts/review_developer.py approve-attest {key_id}",
        ],
    )


async def attest_decided(to: str, key_name: str, approved: bool) -> None:
    await _send(
        to,
        "Attest request approved" if approved else "Attest request declined",
        "Attest request approved" if approved else "Attest request declined",
        [
            f"Records imported with {key_name} now count as verified."
            if approved
            else f"Records imported with {key_name} will keep counting as unverified. Reply to this email to find out more.",
        ],
        ("Open API keys", _url("/developer/keys")),
    )
