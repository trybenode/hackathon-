"""Purpose: Declare the core trust-platform entities, enums, constraints, and relationships.

Dependencies: SQLAlchemy and app.db.base.
Used by: Alembic metadata, repositories, and domain services.
"""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UUIDTimestampMixin


class HistoryStatus(StrEnum):
    BUILDING_HISTORY = "building_history"
    ACTIVE = "active"
    RESTRICTED = "restricted"


class OrganizationType(StrEnum):
    EMPLOYER = "employer"
    PLATFORM = "platform"
    OPERATOR = "operator"


class JobType(StrEnum):
    PLATFORM = "platform"
    INDEPENDENT = "independent"


class JobStatus(StrEnum):
    DRAFT = "draft"
    ACCEPTED = "accepted"
    IN_PROGRESS = "in_progress"
    SUBMITTED = "submitted"
    COMPLETED = "completed"
    DISPUTED = "disputed"
    CANCELLED = "cancelled"
    RELEASED = "released"


class OutcomeStatus(StrEnum):
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    DISPUTED = "disputed"
    NO_SHOW = "no_show"
    UNKNOWN = "unknown"


class CancelledBy(StrEnum):
    WORKER = "worker"
    CLIENT = "client"
    PLATFORM = "platform"


class DisputeResolution(StrEnum):
    OPEN = "open"
    UPHELD = "upheld"
    DISMISSED = "dismissed"


class ImportMethod(StrEnum):
    NATIVE = "native"
    API = "api"
    CSV_UPLOAD = "csv_upload"


class AssessmentStatus(StrEnum):
    BUILDING_HISTORY = "building_history"
    APPROVED = "approved"
    RESTRICTED = "restricted"
    REVIEW_REQUIRED = "review_required"


class AgreementStatus(StrEnum):
    """Guarantor instrument lifecycle.

    Draft -> Pending Signature -> Pending Verification -> Active ->
    Triggered -> (Disputed) -> Paid / Dismissed, or Expired / Revoked.

    A triggered claim is still live work for the guarantor; it ends only when
    it is paid or dismissed.
    Declined covers a guarantor refusing to sign; suspended is reserved for
    administrative holds on an active instrument.
    """

    DRAFT = "draft"
    REQUESTED = "requested"
    PENDING_SIGNATURE = "pending_signature"
    PENDING_VERIFICATION = "pending_verification"
    ACTIVE = "active"
    TRIGGERED = "triggered"
    DISPUTED = "disputed"
    PAID = "paid"
    DISMISSED = "dismissed"
    SUSPENDED = "suspended"
    REVOKED = "revoked"
    EXPIRED = "expired"
    DECLINED = "declined"


class DisputeStatus(StrEnum):
    OPEN = "open"
    UNDER_REVIEW = "under_review"
    RESOLVED = "resolved"
    CLOSED = "closed"


class EscrowStatus(StrEnum):
    PENDING = "pending"
    HELD = "held"
    RELEASED = "released"
    REFUNDED = "refunded"
    FAILED = "failed"


class CredentialStatus(StrEnum):
    ACTIVE = "active"
    REVOKED = "revoked"
    EXPIRED = "expired"


class ProviderOperationStatus(StrEnum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class InsuranceStatus(StrEnum):
    PENDING = "pending"
    ACTIVE = "active"
    EXPIRED = "expired"
    VOIDED = "voided"

#TABLES 
class User(UUIDTimestampMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(160))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    #: Contact details a guarantor maintains on their profile.
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)

    worker: Mapped["Worker | None"] = relationship(back_populates="user")


class Worker(UUIDTimestampMixin, Base):
    __tablename__ = "workers"

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    history_status: Mapped[HistoryStatus] = mapped_column(
        Enum(HistoryStatus, name="history_status"), default=HistoryStatus.BUILDING_HISTORY
    )
    #: What the worker does, e.g. "Cleaner". Shown to guarantors and clients.
    role: Mapped[str | None] = mapped_column(String(80), nullable=True)
    #: Where the worker operates, e.g. "Lekki, Lagos".
    location: Mapped[str | None] = mapped_column(String(160), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    #: A demo worker that only sandbox platform keys can see.
    is_sandbox: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)

    user: Mapped[User] = relationship(back_populates="worker")
    outcomes: Mapped[list["NormalizedOutcome"]] = relationship(back_populates="worker")
    assessments: Mapped[list["TrustAssessment"]] = relationship(back_populates="worker")
    jobs: Mapped[list["Job"]] = relationship(back_populates="worker")


class Organization(UUIDTimestampMixin, Base):
    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(String(200))
    organization_type: Mapped[OrganizationType] = mapped_column(
        Enum(OrganizationType, name="organization_type")
    )


class PlatformConnection(UUIDTimestampMixin, Base):
    __tablename__ = "platform_connections"

    worker_id: Mapped[UUID] = mapped_column(ForeignKey("workers.id", ondelete="CASCADE"))
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))
    provider_account_ref: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    __table_args__ = (
        UniqueConstraint("worker_id", "organization_id", "provider_account_ref"),
    )


class IdentityVerification(UUIDTimestampMixin, Base):
    """A completed check against a KYC provider.

    Holds the provider's reference and outcome only. Identity numbers and
    documents are never stored: they are passed to the provider and dropped.
    """

    __tablename__ = "identity_verifications"

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    provider: Mapped[str] = mapped_column(String(80))
    provider_reference: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(40))
    #: "identity" for the details check, "liveness" for the face check.
    check_type: Mapped[str] = mapped_column(String(40), default="identity")
    #: Object storage key for a supporting document, never the document itself.
    document_reference: Mapped[str | None] = mapped_column(String(500), nullable=True)


class OutcomeSource(UUIDTimestampMixin, Base):
    __tablename__ = "outcome_sources"

    organization_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(120), unique=True)
    normalization_version: Mapped[str] = mapped_column(String(40))


class RawOutcome(UUIDTimestampMixin, Base):
    __tablename__ = "raw_outcomes"

    source_id: Mapped[UUID] = mapped_column(ForeignKey("outcome_sources.id", ondelete="RESTRICT"))
    external_outcome_id: Mapped[str] = mapped_column(String(255))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    payload_checksum: Mapped[str] = mapped_column(String(64))
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint("source_id", "external_outcome_id"),
    )


class NormalizedOutcome(UUIDTimestampMixin, Base):
    __tablename__ = "normalized_outcomes"

    worker_id: Mapped[UUID] = mapped_column(ForeignKey("workers.id", ondelete="CASCADE"))
    job_id: Mapped[UUID | None] = mapped_column(ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True)
    raw_outcome_id: Mapped[UUID] = mapped_column(ForeignKey("raw_outcomes.id", ondelete="RESTRICT"))
    outcome_key: Mapped[str] = mapped_column(String(80))
    status: Mapped[OutcomeStatus] = mapped_column(Enum(OutcomeStatus, name="outcome_status"))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    rating: Mapped[Decimal | None] = mapped_column(Numeric(4, 2), nullable=True)
    amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    completion_confirmed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    quality_flags: Mapped[list[str]] = mapped_column(JSON, default=list)
    dispute_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_urls: Mapped[list[str]] = mapped_column(JSON, default=list)
    normalization_version: Mapped[str] = mapped_column(String(40))
    cancelled_by: Mapped[str | None] = mapped_column(String(20), nullable=True)
    dispute_resolution: Mapped[str | None] = mapped_column(String(20), nullable=True)
    client_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_platform: Mapped[str] = mapped_column(
        String(120), default="legacy", server_default="legacy", nullable=False
    )
    import_method: Mapped[str] = mapped_column(
        String(20), default="native", server_default="native", nullable=False
    )
    verified: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )

    available_signals: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    verification_method: Mapped[str | None] = mapped_column(String(40), nullable=True)
    verified_by_org_id: Mapped[UUID | None] = mapped_column(ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    worker: Mapped[Worker] = relationship(back_populates="outcomes")
    __table_args__ = (
        Index("ix_normalized_outcomes_worker_occurred", "worker_id", "occurred_at"),
        CheckConstraint("rating IS NULL OR (rating >= 0 AND rating <= 5)", name="rating_range"),
        CheckConstraint("amount IS NULL OR amount >= 0", name="amount_nonnegative"),
        CheckConstraint(
            "cancelled_by IS NULL OR cancelled_by IN ('worker', 'client', 'platform')",
            name="cancelled_by_valid",
        ),
        CheckConstraint(
            "dispute_resolution IS NULL OR dispute_resolution IN ('open', 'upheld', 'dismissed')",
            name="dispute_resolution_valid",
        ),
        CheckConstraint(
            "import_method IN ('native', 'api', 'csv_upload')",
            name="import_method_valid",
        ),
    )


class TrustPolicy(UUIDTimestampMixin, Base):
    __tablename__ = "trust_policies"

    name: Mapped[str] = mapped_column(String(120))
    version: Mapped[int] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    rules: Mapped[list["TrustPolicyRule"]] = relationship(back_populates="policy")

    __table_args__ = (UniqueConstraint("name", "version"),)


class TrustPolicyRule(UUIDTimestampMixin, Base):
    __tablename__ = "trust_policy_rules"

    policy_id: Mapped[UUID] = mapped_column(ForeignKey("trust_policies.id", ondelete="CASCADE"))
    signal_key: Mapped[str] = mapped_column(String(100))
    weight: Mapped[Decimal] = mapped_column(Numeric(8, 4))
    threshold: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)

    policy: Mapped[TrustPolicy] = relationship(back_populates="rules")


class TrustAssessment(UUIDTimestampMixin, Base):
    __tablename__ = "trust_assessments"

    worker_id: Mapped[UUID] = mapped_column(ForeignKey("workers.id", ondelete="CASCADE"))
    policy_id: Mapped[UUID] = mapped_column(ForeignKey("trust_policies.id", ondelete="RESTRICT"))
    decision: Mapped[bool] = mapped_column(Boolean)
    confidence: Mapped[Decimal] = mapped_column(Numeric(5, 4))
    #: The weighted score the band is cut from, 0 to 1. Empty when scoring
    #: stopped early (Building History, a failed hard rule).
    score: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    status: Mapped[AssessmentStatus] = mapped_column(Enum(AssessmentStatus, name="assessment_status"))
    band: Mapped[str] = mapped_column(
        String(24), default="Building History", server_default="Building History", nullable=False
    )
    signals_used: Mapped[list[str]] = mapped_column(
        JSON, default=list, server_default="[]", nullable=False
    )
    explanation_summary: Mapped[str] = mapped_column(
        Text, default="", server_default="", nullable=False
    )
    input_fingerprint: Mapped[str] = mapped_column(String(64))
    assessed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default="now()")

    worker: Mapped[Worker] = relationship(back_populates="assessments")
    signals: Mapped[list["TrustAssessmentSignal"]] = relationship(back_populates="assessment")
    __table_args__ = (
        Index("ix_trust_assessments_worker_assessed", "worker_id", "assessed_at"),
        UniqueConstraint("worker_id", "policy_id", "input_fingerprint"),
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="confidence_range"),
        CheckConstraint("score IS NULL OR (score >= 0 AND score <= 1)", name="score_range"),
    )


class TrustAssessmentSignal(UUIDTimestampMixin, Base):
    __tablename__ = "trust_assessment_signals"

    assessment_id: Mapped[UUID] = mapped_column(ForeignKey("trust_assessments.id", ondelete="CASCADE"))
    signal_key: Mapped[str] = mapped_column(String(100))
    signal_value: Mapped[Decimal] = mapped_column(Numeric(10, 4))
    contribution: Mapped[Decimal] = mapped_column(Numeric(10, 4))

    assessment: Mapped[TrustAssessment] = relationship(back_populates="signals")


class Job(UUIDTimestampMixin, Base):
    __tablename__ = "jobs"

    worker_id: Mapped[UUID] = mapped_column(ForeignKey("workers.id", ondelete="RESTRICT"))
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="RESTRICT"))
    job_type: Mapped[JobType] = mapped_column(Enum(JobType, name="job_type"))
    status: Mapped[JobStatus] = mapped_column(Enum(JobStatus, name="job_status"), default=JobStatus.DRAFT)
    client_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=True)
    title: Mapped[str] = mapped_column(String(200))
    agreed_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    auto_release_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    #: Who hired the worker. Clients have no account yet; escrow needs these.
    client_name: Mapped[str | None] = mapped_column(String(300), nullable=True)
    client_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    client_phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    location: Mapped[str | None] = mapped_column(String(160), nullable=True)
    #: Label/value pairs shown on Job Details, e.g. {"label": "Bedrooms", "value": "2"}.
    details: Mapped[list[dict[str, str]]] = mapped_column(
        JSON, default=list, server_default="[]", nullable=False
    )
    #: When the worker said the work was done.
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    #: The secret in the job link the worker shares; it is the customer's
    #: only key to the job, since customers have no account.
    link_token: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    #: When the work is booked for.
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    #: The customer's 1-5 star rating, given when they release the payment.
    rating: Mapped[int | None] = mapped_column(Integer, nullable=True)

    worker: Mapped[Worker] = relationship(back_populates="jobs")
    confirmations: Mapped[list["JobConfirmation"]] = relationship(back_populates="job")
    disputes: Mapped[list["Dispute"]] = relationship(back_populates="job")
    escrow_transactions: Mapped[list["EscrowTransaction"]] = relationship(back_populates="job")
    __table_args__ = (
        CheckConstraint("agreed_amount >= 0", name="agreed_amount_nonnegative"),
        CheckConstraint("rating IS NULL OR (rating >= 1 AND rating <= 5)", name="rating_range"),
    )


class JobConfirmation(UUIDTimestampMixin, Base):
    __tablename__ = "job_confirmations"

    job_id: Mapped[UUID] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"))
    confirmer_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    confirmer_role: Mapped[str] = mapped_column(String(40))
    confirmed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default="now()")
    confirmed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    job: Mapped[Job] = relationship(back_populates="confirmations")
    __table_args__ = (UniqueConstraint("job_id", "confirmer_role"),)


class Dispute(UUIDTimestampMixin, Base):
    __tablename__ = "disputes"

    job_id: Mapped[UUID] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"))
    #: Empty when the customer raised it: customers have no account.
    opened_by_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    #: "customer", "worker", or "timeout" (no code within the confirmation window).
    raised_by: Mapped[str] = mapped_column(String(20), default="worker", server_default="worker")
    reason: Mapped[str] = mapped_column(Text)
    status: Mapped[DisputeStatus] = mapped_column(Enum(DisputeStatus, name="dispute_status"), default=DisputeStatus.OPEN)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    evidence_urls: Mapped[list[str]] = mapped_column(JSON, default=list)

    job: Mapped[Job] = relationship(back_populates="disputes")


class EscrowTransaction(UUIDTimestampMixin, Base):
    __tablename__ = "escrow_transactions"

    job_id: Mapped[UUID] = mapped_column(ForeignKey("jobs.id", ondelete="RESTRICT"))
    provider: Mapped[str] = mapped_column(String(60), default="vesti")
    provider_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3), default="NGN")
    micro_premium: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    cover_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[EscrowStatus] = mapped_column(Enum(EscrowStatus, name="escrow_status"), default=EscrowStatus.PENDING)
    #: Payscrow's GUID for the transaction; only the paid webhook carries it,
    #: and releasing funds needs it.
    provider_transaction_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    #: Where the client pays.
    payment_link: Mapped[str | None] = mapped_column(String(500), nullable=True)
    #: What the client pays: the job plus their share of the escrow charge.
    total_payable: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    funded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    in_dispute: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )
    #: Payscrow's dispute stage and, once ruled, how it was resolved.
    dispute_stage: Mapped[str | None] = mapped_column(String(40), nullable=True)
    resolution_type: Mapped[str | None] = mapped_column(String(20), nullable=True)

    job: Mapped[Job] = relationship(back_populates="escrow_transactions")
    __table_args__ = (CheckConstraint("amount >= 0", name="amount_nonnegative"),)


class GuarantorAgreement(UUIDTimestampMixin, Base):
    __tablename__ = "guarantor_agreements"

    worker_id: Mapped[UUID] = mapped_column(ForeignKey("workers.id", ondelete="CASCADE"))
    #: Unset while a worker's invite link waits for someone to claim it.
    guarantor_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    #: The name the worker gave when inviting, shown until the guarantor signs in.
    guarantor_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    #: The platform that asked for this guarantee through the API; only it may
    #: send, trigger, resolve or revoke it.
    organization_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True
    )
    job_id: Mapped[UUID | None] = mapped_column(ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True)
    scope: Mapped[str] = mapped_column(Text)
    conditions: Mapped[str] = mapped_column(Text)
    relationship_type: Mapped[str] = mapped_column(String(40))
    guarantor_phone: Mapped[str] = mapped_column(String(40), default="")
    guarantor_address: Mapped[str] = mapped_column(String(500), default="")
    status: Mapped[AgreementStatus] = mapped_column(
        Enum(AgreementStatus, name="agreement_status"), default=AgreementStatus.DRAFT
    )
    valid_until: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    signed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    triggered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    #: When a triggered claim was paid or dismissed.
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)

    signatures: Mapped[list["ElectronicSignature"]] = relationship(
        back_populates="agreement", cascade="all, delete-orphan"
    )


class ElectronicSignature(UUIDTimestampMixin, Base):
    __tablename__ = "electronic_signatures"

    agreement_id: Mapped[UUID] = mapped_column(ForeignKey("guarantor_agreements.id", ondelete="CASCADE"))
    agreement: Mapped[GuarantorAgreement] = relationship(back_populates="signatures")
    signer_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    signer_name: Mapped[str] = mapped_column(String(160))
    signer_phone: Mapped[str] = mapped_column(String(40))
    accepted: Mapped[bool] = mapped_column(Boolean)
    ip_address: Mapped[str] = mapped_column(String(64))
    user_agent: Mapped[str] = mapped_column(String(1000))
    signed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    signature_hash: Mapped[str] = mapped_column(String(128))


class Credential(UUIDTimestampMixin, Base):
    __tablename__ = "credentials"

    worker_id: Mapped[UUID] = mapped_column(ForeignKey("workers.id", ondelete="CASCADE"))
    issuer_organization_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True
    )
    credential_type: Mapped[str] = mapped_column(String(80))
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[CredentialStatus] = mapped_column(
        Enum(CredentialStatus, name="credential_status"), default=CredentialStatus.ACTIVE
    )
    payload_hash: Mapped[str] = mapped_column(String(128))
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default="now()")
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CredentialTransfer(UUIDTimestampMixin, Base):
    __tablename__ = "credential_transfers"

    worker_id: Mapped[UUID] = mapped_column(ForeignKey("workers.id", ondelete="CASCADE"))
    credential_id: Mapped[UUID] = mapped_column(ForeignKey("credentials.id", ondelete="CASCADE"))
    direction: Mapped[str] = mapped_column(String(20))
    source_platform: Mapped[str | None] = mapped_column(String(120), nullable=True)
    transfer_token_hash: Mapped[str] = mapped_column(String(128))
    validation_status: Mapped[str] = mapped_column(String(40))

    __table_args__ = (
        UniqueConstraint("worker_id", "direction", "transfer_token_hash"),
    )


class InsurancePolicy(UUIDTimestampMixin, Base):
    __tablename__ = "insurance_policies"

    job_id: Mapped[UUID] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), unique=True)
    provider: Mapped[str] = mapped_column(String(60), default="vesti")
    premium: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    coverage_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    status: Mapped[InsuranceStatus] = mapped_column(
        Enum(InsuranceStatus, name="insurance_status"), default=InsuranceStatus.PENDING
    )
    provider_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)


class ProviderOperation(UUIDTimestampMixin, Base):
    __tablename__ = "provider_operations"

    provider: Mapped[str] = mapped_column(String(60))
    operation_type: Mapped[str] = mapped_column(String(80))
    entity_type: Mapped[str] = mapped_column(String(80))
    entity_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True))
    idempotency_key: Mapped[str] = mapped_column(String(128), unique=True)
    status: Mapped[ProviderOperationStatus] = mapped_column(
        Enum(ProviderOperationStatus, name="provider_operation_status"),
        default=ProviderOperationStatus.PENDING,
    )
    request_payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    response_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)


class AuditEvent(UUIDTimestampMixin, Base):
    __tablename__ = "audit_events"

    actor_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    entity_type: Mapped[str] = mapped_column(String(80))
    entity_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True))
    action: Mapped[str] = mapped_column(String(100))
    event_metadata: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict)

    __table_args__ = (Index("ix_audit_events_entity", "entity_type", "entity_id", "created_at"),)


class LoginCode(UUIDTimestampMixin, Base):
    """A one-time code emailed to a guarantor so they can prove an address.

    Only the hash is stored, so a database leak does not hand out valid codes.
    """

    __tablename__ = "login_codes"

    email: Mapped[str] = mapped_column(String(320), index=True)
    code_hash: Mapped[str] = mapped_column(String(128))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    __table_args__ = (Index("ix_login_codes_email_created", "email", "created_at"),)


class UserSession(UUIDTimestampMixin, Base):
    """A signed-in session, referenced by an HTTP-only cookie.

    The cookie carries a random token; only its hash lives here, so the table
    cannot be used to mint sessions.
    """

    __tablename__ = "user_sessions"

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
