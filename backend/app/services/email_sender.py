"""Purpose: Define the transactional email seam and a development stub.

Dependencies: dataclasses, logging.
Used by: app.services.auth when sending login codes.

Resend will be wired up once API keys exist; until then the stub records what
would have been sent so the flow can be exercised end to end.
"""

from __future__ import annotations

import logging
import ssl
from dataclasses import dataclass
from typing import Protocol

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EmailMessage:
    to: str
    subject: str
    body: str
    #: Optional HTML alternative; clients that cannot render it use `body`.
    html: str | None = None


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


class EmailDeliveryError(Exception):
    """The provider refused the message."""


class ResendEmailSender:
    """Sends through Resend's transactional API.

    Resend only accepts a verified sending domain, or its shared
    `onboarding@resend.dev` address, which can only reach the account owner.
    """

    name = "resend"
    endpoint = "https://api.resend.com/emails"
    timeout = httpx.Timeout(10.0)
    #: One retry rides out a dropped connection.
    attempts = 2

    def __init__(self, api_key: str, sender: str) -> None:
        self.api_key = api_key
        self.sender = sender

    async def send(self, message: EmailMessage) -> None:
        payload: dict[str, object] = {
            "from": self.sender,
            "to": [message.to],
            "subject": message.subject,
            "text": message.body,
        }
        if message.html:
            payload["html"] = message.html

        response = None
        for attempt in range(1, self.attempts + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(
                        self.endpoint,
                        json=payload,
                        headers={"Authorization": f"Bearer {self.api_key}"},
                    )
                break
            # A dropped connection can surface as an httpx error or, mid-TLS,
            # as a raw SSL/OS error; either way it is "not sent", not a crash.
            except (httpx.HTTPError, ssl.SSLError, OSError) as error:
                if attempt == self.attempts:
                    raise EmailDeliveryError(f"Could not reach Resend: {error}") from error

        if response.status_code >= 400:
            # The body explains refusals such as an unverified domain; it does
            # not contain the API key.
            raise EmailDeliveryError(
                f"Resend refused the message ({response.status_code}): {response.text[:300]}"
            )

        # The id makes a specific delivery traceable in the Resend dashboard.
        message_id = response.json().get("id") if response.content else None
        logger.info("Resend accepted mail to %s (id=%s)", message.to, message_id)


def build_default_sender() -> EmailSender:
    """Use Resend when a key is configured, otherwise log the message."""

    settings = get_settings()
    if settings.email_enabled:
        return ResendEmailSender(settings.resend_api_key, settings.resend_from)

    return LoggingEmailSender()


default_email_sender: EmailSender = build_default_sender()
