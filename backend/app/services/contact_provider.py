"""Replaceable request-scoped SMS verification; no general login sessions."""
from dataclasses import dataclass
from typing import Protocol
import re
import httpx
from app.core.config import get_settings
from app.services.feature_common import FeatureError


@dataclass(frozen=True)
class ContactChallenge:
    """Persistable provider reference, separate from the secret challenge code."""
    reference: str
    sandbox: bool


class ContactProvider(Protocol):
    """Send/check contact challenges without storing identity documents."""
    async def send(self, phone: str) -> ContactChallenge: ...
    async def check(self, phone: str, code: str, reference: str) -> bool: ...


class TwilioContactProvider:
    """Use Twilio Verify; all I/O is asynchronous and provider errors are redacted."""
    def __init__(self) -> None:
        cfg = get_settings()
        if not all((cfg.twilio_account_sid, cfg.twilio_auth_token, cfg.twilio_verify_service_sid)):
            raise FeatureError(503, "CONTACT_PROVIDER_UNAVAILABLE", "Contact verification is not configured.")
        self.auth = (cfg.twilio_account_sid, cfg.twilio_auth_token)
        self.base = f"https://verify.twilio.com/v2/Services/{cfg.twilio_verify_service_sid}"

    async def _post(self, path: str, data: dict[str, str]) -> dict:
        async with httpx.AsyncClient(timeout=10) as client:
            try:
                response = await client.post(f"{self.base}/{path}", data=data, auth=self.auth)
                if response.status_code >= 400:
                    raise FeatureError(503, "CONTACT_PROVIDER_UNAVAILABLE", "Contact verification is temporarily unavailable.")
                body = response.json()
                if not isinstance(body, dict):
                    raise ValueError("Invalid provider response")
                return body
            except (httpx.HTTPError, ValueError) as error:
                raise FeatureError(503, "CONTACT_PROVIDER_UNAVAILABLE", "Contact verification is temporarily unavailable.") from error

    async def send(self, phone: str) -> ContactChallenge:
        """Start SMS verification for the stored intended contact."""
        body = await self._post("Verifications", {"To": phone, "Channel": "sms"})
        reference = body.get("sid")
        if not isinstance(reference, str) or not re.fullmatch(r"VE[0-9a-fA-F]{32}", reference):
            raise FeatureError(503, "CONTACT_PROVIDER_UNAVAILABLE", "Contact verification is temporarily unavailable.")
        return ContactChallenge(reference=reference, sandbox=False)

    async def check(self, phone: str, code: str, reference: str) -> bool:
        """Check against the same contact, never a browser-supplied destination."""
        body = await self._post("VerificationCheck", {"VerificationSid": reference, "Code": code})
        return body.get("status") == "approved" and body.get("sid") == reference and body.get("to") == phone


def contact_provider() -> ContactProvider | None:
    """Select configured production provider; only development permits local codes."""
    cfg = get_settings()
    if cfg.sms_provider == "twilio":
        return TwilioContactProvider()
    if cfg.sms_provider == "stub" and cfg.environment == "development":
        return None
    raise FeatureError(503, "CONTACT_PROVIDER_UNAVAILABLE", "A real SMS verification provider is required.")
