"""Purpose: Define the escrow provider seam, the Payscrow client, and a local stand-in.

Dependencies: httpx, hmac/hashlib, and app.core.config.
Used by: app.services.escrow, which drives a job's money through escrow.

Payscrow's marketplace API: we open a transaction and get a payment link for
the client; Payscrow tells us by webhook once the money is held; we release it
by applying the escrow code Payscrow issues for that transaction. Disputes are
raised through us and ruled on by Payscrow.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import time
import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

import httpx

from app.core.config import get_settings

#: Payscrow rejects webhooks older than this, and so do we.
WEBHOOK_TOLERANCE_SECONDS = 300


class EscrowProviderError(Exception):
    """The provider refused the request or could not be reached."""


@dataclass(frozen=True)
class EscrowParty:
    name: str
    email: str
    phone: str | None = None


@dataclass(frozen=True)
class EscrowStart:
    """One job's money going into escrow."""

    reference: str
    description: str
    amount: Decimal
    client: EscrowParty
    worker: EscrowParty
    webhook_url: str | None = None
    return_url: str | None = None
    #: Micro-insurance premium the client pays on top; 0 for none.
    premium: Decimal = Decimal("0")


@dataclass(frozen=True)
class StartedEscrow:
    provider: str
    #: Payscrow's human-readable number, e.g. MKT-00012345.
    transaction_number: str
    payment_link: str
    total_payable: Decimal


@dataclass(frozen=True)
class EscrowState:
    """Payscrow's own view of a transaction (status endpoint)."""

    #: Pending, In Progress, Completed, Finalized or Terminated.
    status: str
    in_escrow: bool
    in_dispute: bool


class EscrowProvider(Protocol):
    name: str

    async def status(self, transaction_number: str) -> EscrowState: ...

    async def start(self, request: EscrowStart) -> StartedEscrow: ...

    async def apply_code(self, transaction_id: str, code: str) -> None: ...

    async def raise_dispute(
        self, transaction_number: str, *, requested_by: str, complaint: str
    ) -> None: ...


class PayscrowProvider:
    """Talks to Payscrow's marketplace API with the broker key."""

    name = "payscrow"

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        merchant_charge_percentage: float = 0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._merchant_charge_percentage = merchant_charge_percentage
        self._transport = transport

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self._base_url,
            headers={"BrokerApiKey": self._api_key, "Content-Type": "application/json"},
            timeout=20,
            transport=self._transport,
        )

    async def _post(self, path: str, body: dict) -> dict:
        try:
            async with self._client() as client:
                response = await client.post(path, json=body)
        except httpx.HTTPError as error:
            raise EscrowProviderError("Could not reach Payscrow.") from error

        payload = response.json() if response.content else {}
        if response.status_code >= 400 or payload.get("success") is False or (
            isinstance(payload.get("data"), dict) and payload["data"].get("isSuccessful") is False
        ) or payload.get("isSuccessful") is False:
            raise EscrowProviderError(_error_message(payload, response.status_code))
        return payload

    async def start(self, request: EscrowStart) -> StartedEscrow:
        body = {
            "transactionReference": request.reference,
            "merchantName": request.worker.name,
            "merchantEmailAddress": request.worker.email,
            "merchantPhoneNo": request.worker.phone,
            "customerName": request.client.name,
            "customerEmailAddress": request.client.email,
            "customerPhoneNo": request.client.phone,
            "currencyCode": "NGN",
            "merchantChargePercentage": self._merchant_charge_percentage,
            "items": [
                {
                    "name": request.description[:300],
                    # Payscrow's docs mark this optional; its API requires it.
                    "description": request.description[:4000],
                    "quantity": 1,
                    "price": float(request.amount),
                }
            ],
        }
        if request.premium > 0:
            # A second line, so the client sees exactly what the cover costs.
            body["items"].append(
                {
                    "name": "Job protection",
                    "description": "Micro-insurance for this job",
                    "quantity": 1,
                    "price": float(request.premium),
                }
            )
        if request.webhook_url:
            body["webhookNotificationUrl"] = request.webhook_url
        if request.return_url:
            body["returnUrl"] = request.return_url

        payload = await self._post(
            "/api/v3/marketplace/transactions/start",
            {key: value for key, value in body.items() if value is not None},
        )
        data = payload.get("data") or {}
        return StartedEscrow(
            provider=self.name,
            transaction_number=data["transactionNumber"],
            payment_link=data["paymentLink"],
            total_payable=Decimal(str(data.get("totalPayable", request.amount))),
        )

    async def status(self, transaction_number: str) -> EscrowState:
        try:
            async with self._client() as client:
                response = await client.get(
                    f"/api/v3/marketplace/transactions/{transaction_number}/status"
                )
        except httpx.HTTPError as error:
            raise EscrowProviderError("Could not reach Payscrow.") from error
        payload = response.json() if response.content else {}
        data = payload.get("data") or {}
        if response.status_code >= 400 or not data:
            raise EscrowProviderError(_error_message(payload, response.status_code))
        return EscrowState(
            status=str(data.get("status", "")),
            in_escrow=bool(data.get("inEscrow")),
            in_dispute=bool(data.get("inDispute")),
        )

    async def apply_code(self, transaction_id: str, code: str) -> None:
        await self._post(
            "/api/v3/escrow/escrowtransactions/applycode",
            {"transactionId": transaction_id, "code": code},
        )

    async def raise_dispute(
        self, transaction_number: str, *, requested_by: str, complaint: str
    ) -> None:
        await self._post(
            f"/api/v3/marketplace/transactions/{transaction_number}/broker/raise-dispute",
            {"requestedBy": requested_by, "complaint": complaint},
        )


def _error_message(payload: dict, status_code: int) -> str:
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    errors = payload.get("errors") or data.get("errors") or []
    # Validation failures come back as {"Field": ["message", ...]}.
    if isinstance(errors, dict) and errors:
        return "; ".join(
            f"{field}: {' '.join(map(str, messages)) if isinstance(messages, list) else messages}"
            for field, messages in errors.items()
        )
    if isinstance(errors, list) and errors:
        return "; ".join(str(error) for error in errors)
    return payload.get("message") or payload.get("title") or f"Payscrow returned {status_code}."


class StubEscrowProvider:
    """Holds money nowhere, for local work and tests.

    Mirrors Payscrow's shape, including the escrow code, so the whole flow runs
    without an account. The "payment link" points nowhere real.
    """

    name = "stub"

    def __init__(self) -> None:
        self.applied: list[tuple[str, str]] = []
        self.disputes: list[tuple[str, str, str]] = []
        #: Transaction numbers the stand-in treats as paid, for tests.
        self.paid: set[str] = set()

    async def status(self, transaction_number: str) -> EscrowState:
        paid = transaction_number in self.paid
        return EscrowState(status="In Progress" if paid else "Pending", in_escrow=paid, in_dispute=False)

    async def start(self, request: EscrowStart) -> StartedEscrow:
        number = f"STUB-{uuid.uuid4().hex[:8].upper()}"
        return StartedEscrow(
            provider=self.name,
            transaction_number=number,
            payment_link=f"https://example.invalid/pay/{number}",
            total_payable=request.amount + request.premium,
        )

    async def apply_code(self, transaction_id: str, code: str) -> None:
        self.applied.append((transaction_id, code))

    async def raise_dispute(
        self, transaction_number: str, *, requested_by: str, complaint: str
    ) -> None:
        self.disputes.append((transaction_number, requested_by, complaint))


def sign_webhook(secret: str, body: bytes, timestamp: int | None = None) -> dict[str, str]:
    """The headers Payscrow sends with a webhook, for tests and simulations."""

    moment = str(timestamp if timestamp is not None else int(time.time()))
    digest = hmac.new(secret.encode(), f"{moment}.".encode() + body, hashlib.sha256).hexdigest()
    return {
        "X-PayScrow-Signature": f"sha256={digest}",
        "X-PayScrow-Timestamp": moment,
        "X-PayScrow-Delivery-Id": str(uuid.uuid4()),
    }


def verify_webhook(
    secret: str, body: bytes, signature: str | None, timestamp: str | None, *, now: float | None = None
) -> bool:
    """Payscrow's scheme: HMAC-SHA256 over "{timestamp}.{raw body}", sent as
    "sha256={hex}", and no older than five minutes."""

    if not secret or not signature or not timestamp:
        return False
    try:
        sent_at = int(timestamp)
    except ValueError:
        return False
    if abs((now if now is not None else time.time()) - sent_at) > WEBHOOK_TOLERANCE_SECONDS:
        return False

    expected = hmac.new(secret.encode(), f"{timestamp}.".encode() + body, hashlib.sha256).hexdigest()
    provided = signature.removeprefix("sha256=")
    return hmac.compare_digest(expected, provided)


def stub_escrow_code() -> str:
    """A 10-character code shaped like Payscrow's."""

    return secrets.token_hex(5).upper()


def build_default_provider() -> EscrowProvider:
    settings = get_settings()
    if settings.escrow_enabled:
        return PayscrowProvider(
            api_key=settings.payscrow_api_key,
            base_url=settings.payscrow_base_url,
            merchant_charge_percentage=settings.payscrow_merchant_charge_percentage,
        )
    return StubEscrowProvider()


#: Late-bound so tests can swap it.
default_escrow_provider: EscrowProvider = build_default_provider()
