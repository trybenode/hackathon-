"""Ownership import/review and additive onboarding contracts; used by routes and worker clients."""

from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Restrictions(StrictModel):
    max_active_jobs: int = Field(1, ge=1, le=100)
    max_job_value: Decimal = Field(Decimal("25000"), gt=0, le=Decimal("100000000"))
    currency: Literal["NGN"] = "NGN"


class OnboardingView(StrictModel):
    action: Literal[
        "additional_verification", "manual_review", "limited", "approved", "declined"
    ]
    requirements: list[str] = Field(default_factory=list)
    reason_codes: list[str] = Field(default_factory=list)
    review_message: str | None = None
    case_id: UUID | None = None
    case_version: int | None = None
    policy_version: int = 1
    evidence_revision: str
    restrictions: Restrictions | None = None
    expires_at: datetime | None = None
    next_steps: list[str] = Field(default_factory=list)


class PolicySettings(StrictModel):
    enabled: bool = False
    allow_limited: bool = True
    allow_approved: bool = True
    approval_days: int = Field(30, ge=1, le=90)
    restrictions: Restrictions = Field(default_factory=Restrictions)


class PolicyUpdate(StrictModel):
    version: int = Field(ge=1)
    settings: PolicySettings


class DecisionInput(StrictModel):
    version: int = Field(ge=1)
    decision: Literal[
        "approve", "approve_limited", "request_information", "decline", "revoke"
    ]
    reason: str = Field(min_length=10, max_length=2000, pattern=r"\S")
    # Ownership approval records the evidence association checked by operations.
    ownership_basis: str | None = Field(default=None, min_length=10, max_length=1000)


class VersionInput(StrictModel):
    version: int = Field(ge=1)


class CaseCreate(StrictModel):
    response: str | None = Field(default=None, min_length=10, max_length=2000)
    organization_id: UUID | None = None
    platform_type: Literal["generic", "domestic", "ride_hailing"] = "generic"


class ImportView(StrictModel):
    id: UUID
    version: int
    source_name: str
    state: str
    row_count: int
    document_present: bool
    expires_at: datetime
    last_reason: str | None
    rows: list[dict]
    ownership_label: str = "History unverified"


class ImportPage(StrictModel):
    items: list[ImportView]
    total: int
    page: int
    size: int
    pages: int


class ProvisionalView(StrictModel):
    rating: float | None
    count: int
    label: str = "Ownership reviewed; history unverified"
    verified: Literal[False] = False


class ReviewRole(StrictModel):
    scope: str
    environment: Literal["production", "sandbox"]


class ReviewAccess(StrictModel):
    roles: list[ReviewRole]


class VerificationCapabilities(StrictModel):
    unsigned_imports_enabled: bool
    additional_verification_enabled: bool
    csv_max_bytes: int
    document_max_bytes: int
    max_rows: int


class PolicyView(StrictModel):
    version: int
    settings: PolicySettings


class ReviewIdentityReference(StrictModel):
    id: UUID
    provider: str
    reference: str
    checked_at: datetime


class ReviewedWorker(StrictModel):
    identity_reference: ReviewIdentityReference | None = None
    id: UUID
    name: str
    email: str
    profile_phone: str | None
    identity: str
    liveness: str


class ImportDetail(StrictModel):
    batch: ImportView
    worker: ReviewedWorker


class ReviewAssessment(StrictModel):
    band: str
    decision: bool
    confidence: float
    score: float | None
    explanation_summary: str
    signals_used: list[str]


class ReviewChecks(StrictModel):
    identity: str
    liveness: str
    guarantor: str


class CaseItem(StrictModel):
    worker_response: str | None
    assessment: ReviewAssessment
    verification: ReviewChecks
    id: UUID
    worker_id: UUID
    display_name: str
    version: int
    state: str
    platform_type: str
    last_reason: str | None
    onboarding: OnboardingView | None
    provisional: ProvisionalView


class CasePage(StrictModel):
    items: list[CaseItem]
    total: int
    page: int
    size: int
    pages: int
