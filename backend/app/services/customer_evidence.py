"""Future payment corroboration must come from authenticated payer/customer mappings."""
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True)
class CustomerEvidence:
    """Corroboration status and references; raw payment/identity documents are excluded."""
    status: str
    reference: str | None = None
    checked_at: datetime | None = None


class CustomerEvidenceProvider(Protocol):
    """A future adapter must validate payment and the actual hiring relationship separately."""
    async def corroborate(self, job_id: UUID, hiring_customer_id: UUID) -> CustomerEvidence: ...


class UnavailableCustomerEvidence:
    """Do not infer customer/payer identity from existing escrow status rows."""
    async def corroborate(self, job_id: UUID, hiring_customer_id: UUID) -> CustomerEvidence:
        """Return unavailable until Software supplies an authenticated mapping contract."""
        return CustomerEvidence(status="not_available")
