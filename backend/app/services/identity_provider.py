"""Purpose: Define the identity-verification provider seam and a local stub.

Dependencies: dataclasses and hashlib.
Used by: app.services.guarantor and app.services.worker_onboarding when a
guarantor or a worker submits identity details.

Identity numbers (NIN, BVN) and documents are passed to a provider and then
dropped. Nothing in this module returns them, and nothing persists them: only
the provider's reference and outcome are stored, per AGENT.md.
"""

from __future__ import annotations

import hashlib
import uuid
from app.core.config import get_settings
from app.services.feature_common import FeatureError
from dataclasses import dataclass
from datetime import date
from typing import Protocol


@dataclass(frozen=True)
class IdentitySubmission:
    """Identity details as entered by a guarantor or a worker.

    Treat every field here as sensitive. It exists to be handed to a provider,
    never to be written to the database or a log.
    """

    first_name: str
    last_name: str
    phone: str
    address: str
    nin: str
    bvn: str
    #: Workers give it; the guarantor form does not ask.
    date_of_birth: date | None = None
    document_filename: str | None = None
    document_size: int | None = None


@dataclass(frozen=True)
class IdentityResult:
    """What a provider tells us, and all we are allowed to keep."""

    provider: str
    reference: str
    status: str

    @property
    def verified(self) -> bool:
        return self.status == "verified"


@dataclass(frozen=True)
class LivenessSubmission:
    """A captured selfie frame, passed to the provider and then dropped."""

    image: bytes
    content_type: str = "image/jpeg"


class IdentityProvider(Protocol):
    """A KYC provider that checks identity details and returns a reference."""

    name: str

    async def verify(self, submission: IdentitySubmission) -> IdentityResult: ...


class LivenessProvider(Protocol):
    """A provider that decides whether a live person is present.

    Standalone: it does not compare against NIN or BVN records, so it can run
    independently of the identity details check.
    """

    name: str

    async def check(self, submission: LivenessSubmission) -> IdentityResult: ...


class StubIdentityProvider:
    """Stands in for a real provider until one is chosen and credentialled.

    Approves any submission that carries a plausibly shaped NIN and BVN, so the
    flow can be exercised end to end. The reference is derived from a random
    UUID, never from the identity numbers, so nothing sensitive leaks into it.
    """

    name = "stub"

    #: Nigerian NIN and BVN are both 11 digits.
    ID_LENGTH = 11

    async def verify(self, submission: IdentitySubmission) -> IdentityResult:
        if get_settings().environment != "development":
            raise FeatureError(503, "IDENTITY_UNAVAILABLE", "Identity verification is not configured.")
        plausible = (
            submission.nin.isdigit()
            and len(submission.nin) == self.ID_LENGTH
            and submission.bvn.isdigit()
            and len(submission.bvn) == self.ID_LENGTH
        )
        return IdentityResult(
            provider=self.name,
            reference=f"STUB-{uuid.uuid4().hex[:16].upper()}",
            status="verified" if plausible else "failed",
        )


class StubLivenessProvider:
    """Stands in for Dojah until credentials exist.

    Approves any frame that carries image data, so the flow can be exercised
    without a provider account. The frame is never stored.
    """

    name = "stub"

    #: Anything smaller than this is not a real capture.
    MIN_FRAME_BYTES = 128

    async def check(self, submission: LivenessSubmission) -> IdentityResult:
        if get_settings().environment != "development":
            raise FeatureError(503, "LIVENESS_UNAVAILABLE", "Liveness verification is not configured.")
        return IdentityResult(
            provider=self.name,
            reference=f"STUB-LIVE-{uuid.uuid4().hex[:12].upper()}",
            status="verified" if len(submission.image) >= self.MIN_FRAME_BYTES else "failed",
        )


class DojahLivenessProvider:
    """Dojah selfie/liveness check.

    Written against the interface but not wired up: it needs DOJAH_APP_ID and
    DOJAH_SECRET_KEY, and a decision on Dojah's sandbox base URL. Swap it for
    the stub in `default_liveness_provider` once those exist.
    """

    name = "dojah"

    def __init__(self, app_id: str, secret_key: str, base_url: str) -> None:
        self.app_id = app_id
        self.secret_key = secret_key
        self.base_url = base_url

    async def check(self, submission: LivenessSubmission) -> IdentityResult:
        raise NotImplementedError(
            "Dojah liveness is not wired up yet: add credentials and implement the call."
        )


def fingerprint(value: str) -> str:
    """Hash an identity number so duplicates can be spotted without storing it.

    Not currently persisted; provided so a future duplicate check never has to
    reach for the raw number.
    """

    return hashlib.sha256(value.strip().encode("utf-8")).hexdigest()


default_provider: IdentityProvider = StubIdentityProvider()
default_liveness_provider: LivenessProvider = StubLivenessProvider()
