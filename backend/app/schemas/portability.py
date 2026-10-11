"""Validated contracts for portable history, consent and restricted reviews."""
from datetime import datetime
from typing import Literal
from uuid import UUID
from pydantic import ConfigDict, Field, model_validator
from app.schemas.api import ApiModel
from app.schemas.history import InformalHistoryCounts


class EvidenceAssessment(ApiModel):
    decision: bool
    band: str
    confidence: float
    status: str
    explanation_summary: str
    signals_used: list[str]
    policy: str = "generic"
    assessed_at: datetime


class IdentitySummary(ApiModel):
    status: Literal["verified", "sandbox", "not_verified"]


class VerificationSummary(ApiModel):
    display_name: str
    role: str | None
    location: str | None
    identity: IdentitySummary
    assessment: EvidenceAssessment
    verified_outcomes: int
    self_declared_outcomes: int
    completed_jobs: int
    completion_rate: float | None
    active_guarantor: bool
    guarantor_sandbox: bool = False
    updated_at: datetime
    informal_history: InformalHistoryCounts = Field(default_factory=InformalHistoryCounts)


class HistoryItem(ApiModel):
    completion_status: str = "Recorded work"
    outcome_id: UUID
    source_record_id: str
    source_platform: str
    source_name: str | None = None
    occurred_at: datetime
    status: str
    rating: float | None
    verified: bool
    verification_method: str | None
    verified_by_org_id: UUID | None
    verified_at: datetime | None
    available_signals: list[str] | None


class WorkerRecord(VerificationSummary):
    worker_id: UUID
    outcomes: list[HistoryItem]
    total_outcomes: int
    starting_rating: float | None
    starting_rating_label: str | None


class GrantResponse(ApiModel):
    operation_id: UUID | None = None
    id: UUID
    created_at: datetime
    expires_at: datetime
    revoked_at: datetime | None
    token: str | None = None
    organization_id: UUID | None = None
    organization_name: str | None = None
    permissions: list[str] | None = None


class GrantList(ApiModel):
    items: list[GrantResponse]
    total: int
    page: int
    size: int
    pages: int


class PlatformOption(ApiModel):
    id: UUID
    name: str


class PlatformCatalog(ApiModel):
    items: list[PlatformOption]
    total: int
    page: int
    size: int
    pages: int


class PlatformGrantRequest(ApiModel):
    organization_id: UUID
    permissions: list[Literal["read_history", "import_history"]] = Field(min_length=1, max_length=2)


class WorkerLinkRequest(ApiModel):
    external_worker_id: str = Field(min_length=1, max_length=120, pattern=r"^[A-Za-z0-9_.-]+$")
    consent_token: str = Field(min_length=32, max_length=128)


class WorkerLinkResponse(ApiModel):
    worker_id: UUID
    external_worker_id: str
    expires_at: datetime


class HistoricalOutcome(ApiModel):
    source_record_id: str = Field(min_length=1, max_length=80)
    occurred_at: datetime
    status: Literal["completed", "cancelled", "no_show"]
    rating: float | None = Field(default=None, ge=1, le=5)
    dispute_resolution: Literal["open", "upheld", "dismissed"] | None = None
    cancelled_by: Literal["worker", "client", "platform"] | None = None
    client_id: str | None = Field(default=None, max_length=120)
    flags: list[Literal["safety", "rework", "damage"]] | None = None
    attest: bool = False

    @model_validator(mode="after")
    def validate_evidence(self):
        if self.occurred_at.tzinfo is None:
            raise ValueError("occurred_at must include a timezone")
        if self.status == "cancelled" and self.attest and self.cancelled_by is None:
            raise ValueError("Attested cancellations require cancelled_by")
        return self


class HistoryImportRequest(ApiModel):
    model_config = ConfigDict(extra="forbid", json_schema_extra={"examples": [{"outcomes": [{"source_record_id": "job-51", "occurred_at": "2026-10-01T12:00:00+01:00", "status": "completed", "dispute_resolution": None, "rating": 4, "attest": False}]}]})
    outcomes: list[HistoricalOutcome] = Field(min_length=1, max_length=100)


class HistoryImportResponse(ApiModel):
    imported_outcomes: int
    duplicate_outcomes: int
    verified_outcomes: int
    status: str = "success"


class HistoryPage(ApiModel):
    items: list[HistoryItem]
    total: int
    page: int
    size: int
    pages: int


class ReviewRequest(ApiModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, json_schema_extra={"examples": [{"rating": 4, "comment": "Completed the agreed work."}]})
    rating: int = Field(ge=1, le=5, strict=True)
    comment: str | None = Field(default=None, max_length=2000)


class ReviewResponse(ApiModel):
    id: UUID
    job_id: UUID
    rating: int
    submitted_at: datetime


class ReviewEligibility(ApiModel):
    job_id: UUID
    job_title: str
    eligible: bool
    reasons: list[str]
    sandbox_identity: bool = False
    existing_review: ReviewResponse | None = None


class ApiError(ApiModel):
    model_config = ConfigDict(extra="forbid", json_schema_extra={"examples": [{"detail": "Worker approval has expired or been revoked.", "code": "CONSENT_EXPIRED"}]})
    detail: str
    code: str


class CustomerJob(ApiModel):
    id: UUID
    title: str
    status: str
    created_at: datetime


class CustomerJobPage(ApiModel):
    items: list[CustomerJob]
    total: int
    page: int
    size: int
    pages: int
