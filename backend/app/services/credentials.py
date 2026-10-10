"""Purpose: Export and import signed, worker-bound portable history credentials.

Dependencies: Python HMAC/base64/JSON, SQLAlchemy, app.models.domain, and API schemas.
Used by: worker credential endpoints; scoring consumes imported records through the shared assessment service.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.domain import (
    Credential,
    CredentialStatus,
    CredentialTransfer,
    NormalizedOutcome,
    OutcomeSource,
    OutcomeStatus,
    RawOutcome,
    TrustAssessment,
    Worker,
)
from app.services.trust_scoring.evidence import scoring_inputs

from app.schemas.api import (
    CredentialsExportResponse,
    TrustSummary,
    VerifiedOutcome,
)

TOKEN_LIFETIME = timedelta(days=7)
# size limits for the signed credential token and its outcome list, to avoid DoS attacks
MAX_TOKEN_LENGTH = 1_000_000
MAX_BUNDLE_OUTCOMES = 1000


class CredentialTokenError(ValueError):
    """A portable credential token is invalid, expired, or untrusted."""


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


# Validates the HMAC signing secret before issuing or verifying portable credentials.
# A secret shorter than 32 characters is treated as unset so the system refuses to sign tokens.
def _validate_secret(secret: str) -> bytes:
    if len(secret) < 32:
        raise CredentialTokenError("Credential signing is not configured")
    return secret.encode("utf-8")

#digitally signs a bundle of verified outcomes for a worker, creating a portable credential token that expires after a set time
def sign_bundle(
    payload: dict[str, Any],
    secret: str,
    *,
    now: datetime | None = None,
    lifetime: timedelta = TOKEN_LIFETIME,
) -> str:
    """Serialize a short-lived payload and authenticate it with HMAC-SHA256."""

    key = _validate_secret(secret)
    issued_at = now or datetime.now(UTC)
    claims = dict(payload)
    claims.setdefault("iss", "dynamic-trust-infrastructure")
    claims["iat"] = int(issued_at.timestamp())
    claims["exp"] = int((issued_at + lifetime).timestamp())
    encoded_payload = _b64encode(
        json.dumps(claims, separators=(",", ":"), sort_keys=True).encode("utf-8")
    )
    signature = _b64encode(hmac.new(key, encoded_payload.encode("ascii"), hashlib.sha256).digest())
    return f"{encoded_payload}.{signature}"

# checks if the seal is perfectly intact, makes sure it hasn't expired, and verifies it was actually issued by a trusted sources
def verify_bundle(
    token: str, secret: str, *, now: datetime | None = None
) -> dict[str, Any]:
    """Verify the token signature and expiration before returning its claims."""

    key = _validate_secret(secret)
    if len(token) > MAX_TOKEN_LENGTH:
        raise CredentialTokenError("Credential token is too large")
    try:
        encoded_payload, encoded_signature = token.split(".", maxsplit=1)
        supplied_signature = _b64decode(encoded_signature)
        expected_signature = hmac.new(
            key, encoded_payload.encode("ascii"), hashlib.sha256
        ).digest()
        if not hmac.compare_digest(supplied_signature, expected_signature):
            raise CredentialTokenError("Credential token signature is invalid")
        claims = json.loads(_b64decode(encoded_payload))
    except CredentialTokenError:
        raise
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise CredentialTokenError("Credential token is malformed") from error

    if not isinstance(claims, dict) or not isinstance(claims.get("exp"), int):
        raise CredentialTokenError("Credential token claims are invalid")
    current_time = int((now or datetime.now(UTC)).timestamp())
    if claims["exp"] <= current_time:
        raise CredentialTokenError("Credential token has expired")
    if claims.get("iss") != "dynamic-trust-infrastructure":
        raise CredentialTokenError("Credential issuer is not trusted")
    if not isinstance(claims.get("outcomes"), list):
        raise CredentialTokenError("Credential outcomes are invalid")
    if len(claims["outcomes"]) > MAX_BUNDLE_OUTCOMES:
        raise CredentialTokenError("Credential contains too many outcomes")
    return claims


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _payload_checksum(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


'''
When "Export My History" is clicked on a platform.
It Checks if worker Id is valid making sure you are a real worker in their database.
It digs into the db and pulls out every single verified job thw worker ever did It also checks their current overall "trust grade."
Then It writes down exactly what happened on every job—when they did it, their rating, and if anyone canceled.
The sign_bundle tool is then used to put all the jobs into a secure, scrambled text file (the "token") and seals it with the secret password.
Log the Transfer: The platform writes in its own private ledger: "On this day, we gave this worker a sealed envelope of their history."
Hand it Over: It hands the sealed text file back to the user to take wherever they want.
'''
async def export_credentials(
    session: AsyncSession,
    worker_id: UUID,
    secret: str,
    *,
    now: datetime | None = None,
) -> CredentialsExportResponse:
    """Create an expiring signed bundle of verified outcomes for one worker."""

    worker = await session.get(Worker, worker_id)
    if worker is None:
        raise CredentialTokenError("Worker not found")

    outcomes = list(
        (
            await session.scalars(
                select(NormalizedOutcome)
                .where(
                    NormalizedOutcome.worker_id == worker_id,
                    NormalizedOutcome.verified.is_(True),
                )
                .order_by(NormalizedOutcome.occurred_at, NormalizedOutcome.id)
            )
        ).all()
    )
    latest_assessment = await session.scalar(
        select(TrustAssessment)
        .where(TrustAssessment.worker_id == worker_id)
        .order_by(TrustAssessment.assessed_at.desc(), TrustAssessment.id.desc())
        .limit(1)
    )

    exported_at = now or datetime.now(UTC)
    credential_id = uuid4()
    outcome_claims: list[dict[str, Any]] = []
    response_outcomes: list[VerifiedOutcome] = []
    inputs = await scoring_inputs(session, outcomes)
    for outcome, evidence in zip(outcomes, inputs, strict=True):
        outcome_claim = {
            "outcome_id": str(outcome.id),
            "outcome_key": outcome.outcome_key,
            "job_id": str(outcome.job_id) if outcome.job_id else None,
            "source_platform": outcome.source_platform,
            "status": evidence["status"],
            "occurred_at": outcome.occurred_at.isoformat(),
            "rating": float(outcome.rating) if outcome.rating is not None else None,
            "cancelled_by": outcome.cancelled_by,
            "dispute_resolution": outcome.dispute_resolution,
            "flags": outcome.quality_flags or [],
            "client_id": outcome.client_id,
            "available_signals": evidence["available_signals"],
            "verification_method": outcome.verification_method,
            "verified_by_org_id": str(outcome.verified_by_org_id) if outcome.verified_by_org_id else None,
            "verified_at": outcome.verified_at.isoformat() if outcome.verified_at else None,
        }
        outcome_claims.append(outcome_claim)
        response_outcomes.append(
            VerifiedOutcome(
                outcome_id=outcome.id,
                job_id=outcome.job_id,
                source_platform=outcome.source_platform,
                status=evidence["status"],
                occurred_at=outcome.occurred_at,
                rating=float(outcome.rating) if outcome.rating is not None else None,
            )
        )

    responsible = [item for item in inputs if "completion_rate" in item["available_signals"] and not (item["status"] == "cancelled" and item["cancelled_by"] in {"client", "platform"})]
    completion_rate = sum(item["status"] == "completed" for item in responsible) / len(responsible) if responsible else None
    token = sign_bundle(
        {
            "iss": "dynamic-trust-infrastructure",
            "jti": str(credential_id),
            "sub": str(worker_id),
            "outcomes": outcome_claims,
        },
        secret,
        now=exported_at,
    )
    token_hash = _token_hash(token)
    band = latest_assessment.band if latest_assessment else "Building History"
    confidence = float(latest_assessment.confidence) if latest_assessment else 0.0

    session.add(
        Credential(
            id=credential_id,
            worker_id=worker_id,
            credential_type="verified_work_history",
            version=1,
            status=CredentialStatus.ACTIVE,
            payload_hash=token_hash,
            issued_at=exported_at,
            expires_at=exported_at + TOKEN_LIFETIME,
        )
    )
    await session.flush()
    session.add(
        CredentialTransfer(
            worker_id=worker_id,
            credential_id=credential_id,
            direction="export",
            transfer_token_hash=token_hash,
            validation_status="valid",
        )
    )
    await session.flush()

    return CredentialsExportResponse(
        worker_id=worker_id,
        exported_at=exported_at,
        trust_summary=TrustSummary(
            band=band,
            confidence=confidence,
            total_jobs=len(outcomes),
            completion_rate=completion_rate,
        ),
        verified_outcomes=response_outcomes,
        credential_token=token,
    )

"""when the sealed envelope is handed back to the platform, it checks the seal, make sure it is still valid, and then copies the contents into the platform's own database"""
async def import_credentials(
    session: AsyncSession,
    worker_id: UUID,
    token: str,
    source_platform: str,
    secret: str,
    *,
    now: datetime | None = None,
) -> int:
    """Verify and import an issued bundle idempotently for its bound worker."""

    claims = verify_bundle(token, secret, now=now)
    if claims.get("sub") != str(worker_id):
        raise CredentialTokenError("Credential belongs to a different worker")

    if await session.get(Worker, worker_id) is None:
        raise CredentialTokenError("Worker not found")

    token_hash = _token_hash(token)
    previous_transfer = await session.scalar(
        select(CredentialTransfer).where(
            CredentialTransfer.worker_id == worker_id,
            CredentialTransfer.direction == "import",
            CredentialTransfer.transfer_token_hash == token_hash,
        )
    )
    if previous_transfer is not None:
        return 0

    try:
        credential_id = UUID(claims["jti"])
    except (KeyError, ValueError, TypeError) as error:
        raise CredentialTokenError("Credential identifier is invalid") from error

    source_name = f"credential-import:{worker_id}"
    source = await session.scalar(select(OutcomeSource).where(OutcomeSource.name == source_name))
    if source is None:
        source = OutcomeSource(name=source_name, normalization_version="credential-v1")
        session.add(source)
        await session.flush()

    imported_credential = Credential(
        worker_id=worker_id,
        credential_type="imported_work_history",
        version=1,
        status=CredentialStatus.ACTIVE,
        payload_hash=token_hash,
        issued_at=now or datetime.now(UTC),
        expires_at=datetime.fromtimestamp(claims["exp"], tz=UTC),
    )
    session.add(imported_credential)
    await session.flush()

    count = 0
    for item in claims["outcomes"]:
        if not isinstance(item, dict):
            raise CredentialTokenError("Credential outcome is malformed")
        try:
            outcome_id = UUID(item["outcome_id"])
            outcome_key = str(item["outcome_key"])
            outcome_status = OutcomeStatus(item["status"])
            occurred_at = datetime.fromisoformat(item["occurred_at"])
            if occurred_at.tzinfo is None:
                occurred_at = occurred_at.replace(tzinfo=UTC)
            source_platform_value = str(item["source_platform"])
            flags = item.get("flags", [])
            if not isinstance(flags, list) or any(not isinstance(flag, str) for flag in flags):
                raise ValueError("invalid flags")
            rating = item.get("rating")
            if rating is not None:
                rating = Decimal(str(rating))
                if rating < 0 or rating > 5:
                    raise ValueError("invalid rating")
            availability = item.get("available_signals")
            if availability is not None and (not isinstance(availability, list) or any(not isinstance(v, str) for v in availability)):
                raise ValueError("invalid signal availability")
            client_id = item.get("client_id")
            if client_id is not None and (not isinstance(client_id, str) or len(client_id) > 255):
                raise ValueError("invalid opaque client identifier")
            verified_by_org_id = UUID(item["verified_by_org_id"]) if item.get("verified_by_org_id") else None
            verified_at = datetime.fromisoformat(item["verified_at"]) if item.get("verified_at") else None
            method = item.get("verification_method")
            if method is not None and (not isinstance(method, str) or len(method) > 40):
                raise ValueError("invalid verification method")
            if not 1 <= len(outcome_key) <= 80 or not 1 <= len(source_platform_value) <= 120:
                raise ValueError("invalid source identifiers")
            cancelled_by = item.get("cancelled_by")
            if cancelled_by not in (None, "worker", "client", "platform"):
                raise ValueError("invalid cancellation source")
            dispute_resolution = item.get("dispute_resolution")
            if dispute_resolution not in (None, "open", "upheld", "dismissed"):
                raise ValueError("invalid dispute resolution")
        except (KeyError, ValueError, TypeError) as error:
            raise CredentialTokenError("Credential outcome is malformed") from error

        row_payload = dict(item)
        existing_outcome = await session.scalar(
            select(NormalizedOutcome).where(
                NormalizedOutcome.worker_id == worker_id,
                NormalizedOutcome.source_platform == source_platform_value,
                NormalizedOutcome.outcome_key == outcome_key,
            )
        )
        if existing_outcome is not None:
            continue
        raw_outcome = RawOutcome(
            source_id=source.id,
            external_outcome_id=f"{credential_id}:{outcome_id}",
            payload=row_payload,
            payload_checksum=_payload_checksum(row_payload),
            received_at=now or datetime.now(UTC),
        )
        session.add(raw_outcome)
        await session.flush()
        session.add(
            NormalizedOutcome(
                worker_id=worker_id,
                raw_outcome_id=raw_outcome.id,
                outcome_key=outcome_key,
                status=outcome_status,
                occurred_at=occurred_at,
                rating=rating,
                quality_flags=flags,
                normalization_version="credential-v1",
                cancelled_by=cancelled_by,
                dispute_resolution=dispute_resolution,
                client_id=client_id,
                available_signals=availability,
                verification_method=method,
                verified_by_org_id=verified_by_org_id,
                verified_at=verified_at,
                source_platform=source_platform_value,
                import_method="api",
                verified=True,
            )
        )
        count += 1

    session.add(
        CredentialTransfer(
            worker_id=worker_id,
            credential_id=imported_credential.id,
            direction="import",
            source_platform=source_platform,
            transfer_token_hash=token_hash,
            validation_status="valid",
        )
    )
    await session.flush()
    return count
