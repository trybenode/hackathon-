"""Purpose: Define the identity-verification provider seam and a local stub.

Dependencies: dataclasses and hashlib.
Used by: app.services.guarantor when a guarantor submits identity details.

Identity numbers (NIN, BVN) and documents are passed to a provider and then
dropped. Nothing in this module returns them, and nothing persists them: only
the provider's reference and outcome are stored, per AGENT.md.
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class IdentitySubmission:
    """Identity details as entered by a guarantor.

    Treat every field here as sensitive. It exists to be handed to a provider,
    never to be written to the database or a log.
    """

    first_name: str
    last_name: str
    phone: str
    address: str
    nin: str
    bvn: str
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


class IdentityProvider(Protocol):
    """A KYC provider that checks identity details and returns a reference."""

    name: str

    async def verify(self, submission: IdentitySubmission) -> IdentityResult: ...


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


def fingerprint(value: str) -> str:
    """Hash an identity number so duplicates can be spotted without storing it.

    Not currently persisted; provided so a future duplicate check never has to
    reach for the raw number.
    """

    return hashlib.sha256(value.strip().encode("utf-8")).hexdigest()


default_provider: IdentityProvider = StubIdentityProvider()
