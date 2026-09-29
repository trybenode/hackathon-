"""Purpose: Define Pydantic request and response contracts from API_Schema.md.

Dependencies: Pydantic and Python standard-library typing/date/UUID types.
Used by: FastAPI route handlers and generated OpenAPI documentation.
"""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PlatformType(StrEnum):
    DOMESTIC = "domestic"
    HANDYMAN = "handyman"
    RIDE_HAILING = "ride_hailing"
    GENERIC = "generic"


class ValueBand(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class TrustStatus(StrEnum):
    SCORED = "Scored"
    BUILDING_HISTORY = "Building History"


class OutcomeStatus(StrEnum):
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    DISPUTED = "disputed"
    NO_SHOW = "no_show"


class GuarantorRelationship(StrEnum):
    SIBLING = "sibling"
    PARENT = "parent"
    SPOUSE = "spouse"
    COLLEAGUE = "colleague"
    OTHER = "other"


class Party(StrEnum):
    CLIENT = "client"
    WORKER = "worker"


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class JobContext(ApiModel):
    job_type: str = Field(min_length=1, max_length=80)
    value_band: ValueBand


class RawSignals(ApiModel):
    completion_rate: Decimal | None = Field(default=None, ge=0, le=1)
    total_jobs: int | None = Field(default=None, ge=0)
    disputes: int | None = Field(default=None, ge=0)
    no_shows: int | None = Field(default=None, ge=0)
    repeat_hires: int | None = Field(default=None, ge=0)
    average_rating: Decimal | None = Field(default=None, ge=0, le=5)
    cancellations: int | None = Field(default=None, ge=0)
    custom_fields: dict[str, object] = Field(default_factory=dict)


class TrustQueryRequest(ApiModel):
    worker_id: UUID
    platform_type: PlatformType
    job_context: JobContext
    raw_signals: RawSignals | None = None


class TrustQueryResponse(ApiModel):
    worker_id: UUID
    decision: bool
    confidence: Decimal = Field(ge=0, le=1)
    band: str
    status: TrustStatus
    signals_used: list[str]
    explanation_summary: str
    platform_type_applied: PlatformType


class TrustBaselines(ApiModel):
    min_completion_rate: Decimal = Field(ge=0, le=1)
    max_dispute_rate: Decimal = Field(ge=0, le=1)
    min_jobs_for_scoring: int = Field(ge=0)


class TrustWeights(ApiModel):
    completion_rate: Decimal = Field(ge=0, le=1)
    dispute_count: Decimal = Field(ge=0, le=1)
    repeat_hires: Decimal = Field(ge=0, le=1)
    average_rating: Decimal = Field(ge=0, le=1)
    no_shows: Decimal = Field(ge=0, le=1)

    @field_validator("no_shows")
    @classmethod
    def weights_sum_is_valid(cls, value: Decimal, info: object) -> Decimal:
        return value


class TrustConfigureRequest(ApiModel):
    platform_id: UUID
    platform_type: PlatformType
    baselines: TrustBaselines
    weights: TrustWeights


class TrustConfigureResponse(ApiModel):
    platform_id: UUID
    status: str = "updated"
    applied_at: datetime


class OutcomePayload(ApiModel):
    status: OutcomeStatus
    rating: Decimal | None = Field(default=None, ge=0, le=5)
    completion_confirmed: bool = False
    quality_flags: list[str] = Field(default_factory=list)
    dispute_reason: str | None = None
    evidence_urls: list[str] = Field(default_factory=list)
    completed_at: datetime | None = None


class OutcomeCreateRequest(ApiModel):
    worker_id: UUID
    job_id: UUID
    platform_id: UUID
    platform_type: PlatformType
    outcome: OutcomePayload
    raw_payload: dict[str, object] = Field(default_factory=dict)


class TrustUpdate(ApiModel):
    previous_band: str | None = None
    new_band: str
    confidence: Decimal = Field(ge=0, le=1)


class OutcomeCreateResponse(ApiModel):
    outcome_id: UUID
    worker_id: UUID
    trust_update: TrustUpdate
    recorded_at: datetime


class GuarantorDetails(ApiModel):
    full_name: str = Field(min_length=1, max_length=160)
    phone: str = Field(min_length=5, max_length=40)
    email: str
    relationship: GuarantorRelationship
    address: str = Field(min_length=1, max_length=500)


class GuarantorInstrumentCreateRequest(ApiModel):
    worker_id: UUID
    guarantor: GuarantorDetails
    job_id: UUID | None = None
    scope: str = Field(min_length=1, max_length=1000)
    conditions: str = Field(min_length=1, max_length=2000)
    valid_until: datetime
    #: Keep the instrument in Draft instead of sending it for signature.
    as_draft: bool = False


class GuarantorInstrumentCreateResponse(ApiModel):
    instrument_id: UUID
    status: str = "Pending Signature"
    worker_id: UUID
    guarantor_name: str
    created_at: datetime
    sign_url: str | None = None


class SignatureMetadata(ApiModel):
    ip: str
    user_agent: str = Field(min_length=1, max_length=1000)
    timestamp: datetime


class GuarantorSignRequest(ApiModel):
    signer_name: str = Field(min_length=1, max_length=160)
    signer_phone: str = Field(min_length=5, max_length=40)
    accepted: bool
    signature_metadata: SignatureMetadata


class GuarantorSignResponse(ApiModel):
    instrument_id: UUID
    status: str = "Pending Verification"
    signed_at: datetime


class GuarantorVerifyRequest(ApiModel):
    """Result of the guarantor's identity check, from the provider."""

    provider: str = Field(min_length=1, max_length=80)
    provider_reference: str = Field(min_length=1, max_length=255)


class GuarantorTriggerRequest(ApiModel):
    reason: str = Field(min_length=1, max_length=500)


class GuarantorRevokeRequest(ApiModel):
    reason: str = Field(min_length=1, max_length=500)


class GuarantorSummary(ApiModel):
    full_name: str
    relationship: str
    phone: str | None = None
    email: str | None = None


class GuarantorInstrumentResponse(ApiModel):
    instrument_id: UUID
    worker_id: UUID
    guarantor: GuarantorSummary
    scope: str
    conditions: str
    status: str
    signed_at: datetime | None = None
    valid_until: datetime
    job_id: UUID | None = None
    verified_at: datetime | None = None
    triggered_at: datetime | None = None
    status_reason: str | None = None
    created_at: datetime | None = None


class GuarantorInstrumentListResponse(ApiModel):
    items: list[GuarantorInstrumentResponse]


class TrustSummary(ApiModel):
    band: str
    confidence: Decimal = Field(ge=0, le=1)
    total_jobs: int = Field(ge=0)
    completion_rate: Decimal = Field(ge=0, le=1)


class VerifiedOutcome(ApiModel):
    job_id: UUID
    platform_type: PlatformType
    status: OutcomeStatus
    rating: Decimal | None = Field(default=None, ge=0, le=5)
    completed_at: datetime | None = None


class CredentialsExportResponse(ApiModel):
    worker_id: UUID
    exported_at: datetime
    trust_summary: TrustSummary
    verified_outcomes: list[VerifiedOutcome]
    credential_token: str


class CredentialsImportRequest(ApiModel):
    credential_token: str = Field(min_length=1)
    source_platform: str = Field(min_length=1, max_length=120)


class CredentialsImportResponse(ApiModel):
    worker_id: UUID
    imported_outcomes: int = Field(ge=0)
    new_band: str
    status: str = "success"


class EscrowCreateRequest(ApiModel):
    amount: Decimal = Field(gt=0)
    currency: str = Field(min_length=3, max_length=3)
    micro_premium: Decimal = Field(ge=0)
    worker_id: UUID
    client_id: UUID


class EscrowCreateResponse(ApiModel):
    escrow_id: UUID
    vesti_reference: str | None = None
    status: str = "Pending Premium"
    cover_active: bool = False


class EscrowPremiumResponse(ApiModel):
    escrow_id: UUID
    status: str = "Active"
    cover_active: bool = True
    activated_at: datetime


class EscrowDetailsResponse(ApiModel):
    escrow_id: UUID
    status: str
    cover_active: bool
    amount: Decimal = Field(gt=0)
    micro_premium: Decimal = Field(ge=0)


class JobConfirmationRequest(ApiModel):
    party: Party
    confirmed: bool
    notes: str | None = None


class JobConfirmationResponse(ApiModel):
    job_id: UUID
    client_confirmed: bool
    worker_confirmed: bool
    status: str
    auto_release_at: datetime | None = None


class JobDisputeRequest(ApiModel):
    raised_by: Party
    reason: str = Field(min_length=1, max_length=2000)
    evidence_urls: list[str] = Field(default_factory=list)


class JobDisputeResponse(ApiModel):
    job_id: UUID
    status: str = "Disputed"
    funds_held: bool = True


class WorkerStats(ApiModel):
    total_jobs: int = Field(ge=0)
    completion_rate: Decimal = Field(ge=0, le=1)
    disputes: int = Field(ge=0)


class WorkerTrust(ApiModel):
    decision: bool
    confidence: Decimal = Field(ge=0, le=1)
    band: str
    status: TrustStatus


class WorkerSummaryResponse(ApiModel):
    worker_id: UUID
    trust: WorkerTrust
    stats: WorkerStats
    active_guarantor: bool
