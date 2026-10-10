"""Verify signed portable credential token integrity and expiration."""

from datetime import UTC, datetime, timedelta

import pytest

from app.services.credentials import CredentialTokenError, sign_bundle, verify_bundle


def test_signed_credential_bundle_round_trips() -> None:
    now = datetime(2026, 10, 3, tzinfo=UTC)
    payload = {"sub": "worker-1", "outcomes": []}

    token = sign_bundle(payload, "a" * 32, now=now, lifetime=timedelta(hours=1))

    assert verify_bundle(token, "a" * 32, now=now)["sub"] == "worker-1"


def test_signed_credential_bundle_rejects_tampering() -> None:
    token = sign_bundle({"sub": "worker-1"}, "a" * 32)
    payload, signature = token.split(".")
    altered = f"{payload[:-1]}{'A' if payload[-1] != 'A' else 'B'}.{signature}"

    with pytest.raises(CredentialTokenError):
        verify_bundle(altered, "a" * 32)


def test_signed_credential_bundle_rejects_expired_tokens() -> None:
    issued = datetime(2026, 10, 1, tzinfo=UTC)
    token = sign_bundle(
        {"sub": "worker-1"},
        "a" * 32,
        now=issued,
        lifetime=timedelta(hours=1),
    )

    with pytest.raises(CredentialTokenError, match="expired"):
        verify_bundle(token, "a" * 32, now=issued + timedelta(hours=2))


def test_non_ascii_token_is_rejected_cleanly() -> None:
    with pytest.raises(CredentialTokenError, match="malformed"):
        verify_bundle("é.payload", "a" * 32)
