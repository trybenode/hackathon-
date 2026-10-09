"""Purpose: Verify the Payscrow client speaks Payscrow's API and webhook signing.

Dependencies: pytest, httpx MockTransport, and app.services.escrow_provider.
Used by: the backend test suite and CI. Never reaches Payscrow.
"""

import json
from dataclasses import replace
from decimal import Decimal

import httpx
import pytest

from app.services.escrow_provider import (
    EscrowParty,
    EscrowProviderError,
    EscrowStart,
    PayscrowProvider,
    sign_webhook,
    verify_webhook,
)

START = EscrowStart(
    reference="JOB-123",
    description="Home cleaning",
    amount=Decimal("25000.00"),
    client=EscrowParty("Peter James", "peter@example.com", "08012345678"),
    worker=EscrowParty("Jane Adams", "jane@example.com", None),
    webhook_url="https://api.example.com/api/v1/webhooks/payscrow",
)


def provider_with(handler) -> PayscrowProvider:
    return PayscrowProvider(
        api_key="test-broker-key",
        base_url="https://api.payscrow.dev",
        transport=httpx.MockTransport(handler),
    )


async def test_start_sends_the_job_and_reads_the_payment_link() -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["key"] = request.headers.get("BrokerApiKey")
        seen["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "success": True,
                "data": {
                    "transactionNumber": "MKT-00012345",
                    "paymentLink": "https://payscrow.dev/MarketPlace/Pay?transId=XYZ",
                    "totalPayable": 25500.0,
                    "currencyCode": "NGN",
                    "errors": [],
                    "isSuccessful": True,
                },
            },
        )

    started = await provider_with(handler).start(START)

    assert seen["path"] == "/api/v3/marketplace/transactions/start"
    assert seen["key"] == "test-broker-key"
    body = seen["body"]
    assert body["transactionReference"] == "JOB-123"
    assert body["merchantEmailAddress"] == "jane@example.com"
    assert body["customerPhoneNo"] == "08012345678"
    assert body["items"] == [
        {"name": "Home cleaning", "description": "Home cleaning", "quantity": 1, "price": 25000.0}
    ]
    assert body["webhookNotificationUrl"].endswith("/webhooks/payscrow")
    # No phone for the worker: the optional field is left out, not sent empty.
    assert "merchantPhoneNo" not in body
    assert started.transaction_number == "MKT-00012345"
    assert started.total_payable == Decimal("25500.0")


async def test_premium_is_a_second_checkout_line() -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["items"] = json.loads(request.content)["items"]
        return httpx.Response(
            200,
            json={
                "success": True,
                "data": {
                    "transactionNumber": "MKT-1",
                    "paymentLink": "https://payscrow.dev/pay",
                    "totalPayable": 26010.0,
                    "isSuccessful": True,
                },
            },
        )

    await provider_with(handler).start(replace(START, premium=Decimal("500.00")))

    assert [item["name"] for item in seen["items"]] == ["Home cleaning", "Job protection"]
    assert seen["items"][1]["price"] == 500.0


async def test_payscrow_errors_surface_with_their_message() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400, json={"success": False, "errors": ["customerPhoneNo is invalid"]}
        )

    with pytest.raises(EscrowProviderError, match="customerPhoneNo is invalid"):
        await provider_with(handler).start(START)


async def test_field_validation_errors_name_the_field() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400,
            json={
                "title": "One or more validation errors occurred.",
                "status": 400,
                "errors": {"Items[0].Description": ["The Description field is required."]},
            },
        )

    with pytest.raises(EscrowProviderError, match="Items\\[0\\].Description: The Description"):
        await provider_with(handler).start(START)


async def test_apply_code_and_dispute_hit_their_endpoints() -> None:
    calls: list[tuple[str, dict]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.url.path, json.loads(request.content)))
        return httpx.Response(200, json={"isSuccessful": True, "errors": []})

    provider = provider_with(handler)
    await provider.apply_code("3fa85f64-5717-4562-b3fc-2c963f66afa6", "ABC123DEF4")
    await provider.raise_dispute("MKT-1", requested_by="merchant", complaint="Client denied access.")

    assert calls[0] == (
        "/api/v3/escrow/escrowtransactions/applycode",
        {"transactionId": "3fa85f64-5717-4562-b3fc-2c963f66afa6", "code": "ABC123DEF4"},
    )
    assert calls[1][0] == "/api/v3/marketplace/transactions/MKT-1/broker/raise-dispute"
    assert calls[1][1]["requestedBy"] == "merchant"


async def test_unreachable_payscrow_is_a_provider_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route", request=request)

    with pytest.raises(EscrowProviderError, match="Could not reach Payscrow"):
        await provider_with(handler).apply_code("id", "CODE123456")


def test_webhook_signature_round_trip() -> None:
    body = b'{"transactionNumber":"MKT-1"}'
    headers = sign_webhook("secret", body, timestamp=1_000_000)

    assert verify_webhook(
        "secret", body, headers["X-PayScrow-Signature"], headers["X-PayScrow-Timestamp"], now=1_000_010
    )
    # Tampered body, wrong secret, or a stale timestamp all fail.
    assert not verify_webhook(
        "secret", body + b" ", headers["X-PayScrow-Signature"], headers["X-PayScrow-Timestamp"], now=1_000_010
    )
    assert not verify_webhook(
        "other", body, headers["X-PayScrow-Signature"], headers["X-PayScrow-Timestamp"], now=1_000_010
    )
    assert not verify_webhook(
        "secret", body, headers["X-PayScrow-Signature"], headers["X-PayScrow-Timestamp"], now=1_000_400
    )
    assert not verify_webhook("", body, headers["X-PayScrow-Signature"], headers["X-PayScrow-Timestamp"])
