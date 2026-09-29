"""Purpose: Define the transactional email seam and a development stub.

Dependencies: dataclasses, logging.
Used by: app.services.auth when sending login codes.

Resend will be wired up once API keys exist; until then the stub records what
would have been sent so the flow can be exercised end to end.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Protocol

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EmailMessage:
    to: str
    subject: str
    body: str


class EmailSender(Protocol):
    """Sends transactional mail."""

    name: str

    async def send(self, message: EmailMessage) -> None: ...


class LoggingEmailSender:
    """Logs the message instead of sending it.

    Keeps local development working without an email account. The login code
    appears in the API log, which is how you read it while testing.
    """

    name = "logging"

    def __init__(self) -> None:
        self.sent: list[EmailMessage] = []

    async def send(self, message: EmailMessage) -> None:
        self.sent.append(message)
        logger.info("Email to %s: %s\n%s", message.to, message.subject, message.body)


class ResendEmailSender:
    """Resend's transactional API.

    Written against the interface but not wired up: it needs RESEND_API_KEY and
    a verified sending domain. Swap it into `default_email_sender` once those
    exist.
    """

    name = "resend"

    def __init__(self, api_key: str, sender: str) -> None:
        self.api_key = api_key
        self.sender = sender

    async def send(self, message: EmailMessage) -> None:
        raise NotImplementedError(
            "Resend is not wired up yet: add RESEND_API_KEY and implement the call."
        )


default_email_sender: EmailSender = LoggingEmailSender()
