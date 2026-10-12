"""Purpose: Persist developer accounts, their verification review, and API usage.

Dependencies: SQLAlchemy and app.db.base.
Used by: app.services.developers and the developer dashboard endpoints.

Documents are kept as object-storage references only; the review itself is
done by an operator (scripts/review_developer.py).
"""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import JSON, DateTime, Enum, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDTimestampMixin


class ReviewStatus(StrEnum):
    NOT_STARTED = "not_started"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    REJECTED = "rejected"


class DeveloperAccount(UUIDTimestampMixin, Base):
    """A developer's KYC (who they are) and KYB (their registered business)."""

    __tablename__ = "developer_accounts"

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    #: The platform organization, made when an operator approves the business.
    organization_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True
    )
    kyc_status: Mapped[ReviewStatus] = mapped_column(
        Enum(ReviewStatus, name="review_status"), default=ReviewStatus.NOT_STARTED
    )
    kyb_status: Mapped[ReviewStatus] = mapped_column(
        Enum(ReviewStatus, name="review_status"), default=ReviewStatus.NOT_STARTED
    )
    #: Why an operator rejected the submission, shown to the developer.
    review_note: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Step 1: identity.
    full_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    id_document_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    id_document_reference: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Step 2: business.
    business_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    business_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    registration_number: Mapped[str | None] = mapped_column(String(40), nullable=True)
    tax_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    cac_document_reference: Mapped[str | None] = mapped_column(String(500), nullable=True)

    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class NameChangeRequest(UUIDTimestampMixin, Base):
    """A developer asking to correct the name their identity check verified."""

    __tablename__ = "developer_name_changes"

    account_id: Mapped[UUID] = mapped_column(ForeignKey("developer_accounts.id", ondelete="CASCADE"), index=True)
    current_name: Mapped[str] = mapped_column(String(160))
    new_name: Mapped[str] = mapped_column(String(160))
    reason: Mapped[str] = mapped_column(String(40))
    document_reference: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[ReviewStatus] = mapped_column(
        Enum(ReviewStatus, name="review_status"), default=ReviewStatus.UNDER_REVIEW
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ApiRequestLog(UUIDTimestampMixin, Base):
    """One call made with a platform key: what, when and how it ended. No bodies."""

    __tablename__ = "api_request_logs"

    platform_key_id: Mapped[UUID] = mapped_column(ForeignKey("platform_keys.id", ondelete="CASCADE"), index=True)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    method: Mapped[str] = mapped_column(String(10))
    #: The route template, e.g. /api/v1/platform/workers/{external_id}/history,
    #: so worker identifiers never land in the log.
    path: Mapped[str] = mapped_column(String(300))
    status_code: Mapped[int] = mapped_column(Integer)
    duration_ms: Mapped[int] = mapped_column(Integer)


class ScoringConfig(UUIDTimestampMixin, Base):
    """A platform's own scoring settings for one platform type (SRS FR-1.3).

    Kept per environment, so a sandbox key can experiment without changing how
    production keys score real workers. Without a row the preset applies.
    """

    __tablename__ = "scoring_configs"
    __table_args__ = (UniqueConstraint("organization_id", "environment", "platform_type"),)

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    environment: Mapped[str] = mapped_column(String(20))
    platform_type: Mapped[str] = mapped_column(String(40))
    #: Signal -> weight; the weights add up to 1.
    weights: Mapped[dict[str, float]] = mapped_column(JSON)
    required_signals: Mapped[list[str]] = mapped_column(JSON)
    #: Signal -> highest raw rate allowed before the worker fails outright.
    hard_fail: Mapped[dict[str, float]] = mapped_column(JSON, default=dict)
    min_jobs: Mapped[int] = mapped_column(Integer)
    high_threshold: Mapped[float] = mapped_column(Float)
    medium_threshold: Mapped[float] = mapped_column(Float)
