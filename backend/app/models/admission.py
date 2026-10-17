"""Private ownership imports and tenant onboarding decisions; used by review services and Alembic."""

from datetime import datetime
from uuid import UUID
from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base, UUIDTimestampMixin


class ReviewMembership(UUIDTimestampMixin, Base):
    __tablename__ = "review_memberships"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "scope", "environment", name="uq_review_membership_scope"
        ),
    )
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    scope: Mapped[str] = mapped_column(String(40))
    environment: Mapped[str] = mapped_column(String(20), default="production")
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class OwnershipImport(UUIDTimestampMixin, Base):
    __tablename__ = "ownership_imports"
    __table_args__ = (
        UniqueConstraint(
            "worker_id", "operation_id", name="uq_ownership_import_operation"
        ),
    )
    worker_id: Mapped[UUID] = mapped_column(
        ForeignKey("workers.id", ondelete="CASCADE"), index=True
    )
    operation_id: Mapped[UUID] = mapped_column(nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64))
    source_name: Mapped[str] = mapped_column(String(120))
    rows: Mapped[list[dict]] = mapped_column(JSON)
    state: Mapped[str] = mapped_column(String(30), default="preparing")
    version: Mapped[int] = mapped_column(Integer, default=1)
    replaces_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("ownership_imports.id"), nullable=True
    )
    document_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    document_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    document_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class ProvisionalRecord(UUIDTimestampMixin, Base):
    __tablename__ = "provisional_records"
    __table_args__ = (
        UniqueConstraint(
            "worker_id", "source_key", name="uq_provisional_source_record"
        ),
    )
    worker_id: Mapped[UUID] = mapped_column(
        ForeignKey("workers.id", ondelete="CASCADE")
    )
    batch_id: Mapped[UUID] = mapped_column(
        ForeignKey("ownership_imports.id", ondelete="RESTRICT")
    )
    source_key: Mapped[str] = mapped_column(String(64))
    payload_hash: Mapped[str] = mapped_column(String(64))
    details: Mapped[dict] = mapped_column(JSON)


class OnboardingPolicy(UUIDTimestampMixin, Base):
    __tablename__ = "onboarding_policies"
    __table_args__ = (
        UniqueConstraint(
            "scope", "environment", "platform_type", name="uq_onboarding_policy_scope"
        ),
    )
    scope: Mapped[str] = mapped_column(String(40))
    environment: Mapped[str] = mapped_column(String(20))
    platform_type: Mapped[str] = mapped_column(String(30), default="generic")
    version: Mapped[int] = mapped_column(Integer, default=1)
    settings: Mapped[dict] = mapped_column(JSON)


class OnboardingCase(UUIDTimestampMixin, Base):
    __tablename__ = "onboarding_cases"
    __table_args__ = (
        UniqueConstraint(
            "worker_id",
            "scope",
            "environment",
            "platform_type",
            name="uq_onboarding_case_scope",
        ),
    )
    worker_id: Mapped[UUID] = mapped_column(
        ForeignKey("workers.id", ondelete="CASCADE")
    )
    scope: Mapped[str] = mapped_column(String(40))
    environment: Mapped[str] = mapped_column(String(20))
    platform_type: Mapped[str] = mapped_column(String(30), default="generic")
    version: Mapped[int] = mapped_column(Integer, default=1)
    policy_version: Mapped[int] = mapped_column(Integer)
    evidence_revision: Mapped[str] = mapped_column(String(64))
    state: Mapped[str] = mapped_column(String(30), default="pending")
    last_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    worker_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    restrictions: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class ReviewDecision(UUIDTimestampMixin, Base):
    __tablename__ = "review_decisions"
    actor_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    entity_type: Mapped[str] = mapped_column(String(30))
    entity_id: Mapped[UUID] = mapped_column(nullable=False)
    version: Mapped[int] = mapped_column(Integer)
    decision: Mapped[str] = mapped_column(String(30))
    reason: Mapped[str] = mapped_column(Text)
    evidence_revision: Mapped[str] = mapped_column(String(64))
    policy_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
