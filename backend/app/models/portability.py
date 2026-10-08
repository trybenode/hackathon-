"""Persistence for consent, platform isolation, idempotency, and restricted reviews."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDTimestampMixin


class PlatformKey(UUIDTimestampMixin, Base):
    __tablename__ = "platform_keys"
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))
    key_hash: Mapped[str] = mapped_column(String(64), unique=True)
    can_attest: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ShareGrant(UUIDTimestampMixin, Base):
    __tablename__ = "share_grants"
    worker_id: Mapped[UUID] = mapped_column(ForeignKey("workers.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PlatformGrant(UUIDTimestampMixin, Base):
    __tablename__ = "platform_grants"
    worker_id: Mapped[UUID] = mapped_column(ForeignKey("workers.id", ondelete="CASCADE"), index=True)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    permissions: Mapped[list[str]] = mapped_column(JSON)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class WorkerLink(UUIDTimestampMixin, Base):
    __tablename__ = "worker_links"
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))
    worker_id: Mapped[UUID] = mapped_column(ForeignKey("workers.id", ondelete="CASCADE"))
    external_worker_id: Mapped[str] = mapped_column(String(120))
    grant_id: Mapped[UUID] = mapped_column(ForeignKey("platform_grants.id", ondelete="CASCADE"))
    __table_args__ = (UniqueConstraint("organization_id", "external_worker_id"),)


class ImportReceipt(UUIDTimestampMixin, Base):
    __tablename__ = "import_receipts"
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))
    worker_id: Mapped[UUID] = mapped_column(ForeignKey("workers.id", ondelete="CASCADE"))
    idempotency_key: Mapped[str] = mapped_column(String(128))
    payload_hash: Mapped[str] = mapped_column(String(64))
    result: Mapped[dict] = mapped_column(JSON)
    __table_args__ = (UniqueConstraint("organization_id", "idempotency_key"),)


class HistoryIdentity(UUIDTimestampMixin, Base):
    """Stable source identity, separate from transferable credential metadata."""
    __tablename__ = "history_identities"
    worker_id: Mapped[UUID] = mapped_column(ForeignKey("workers.id", ondelete="CASCADE"))
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="RESTRICT"))
    source_record_id: Mapped[str] = mapped_column(String(80))
    payload_hash: Mapped[str] = mapped_column(String(64))
    outcome_id: Mapped[UUID] = mapped_column(ForeignKey("normalized_outcomes.id", ondelete="CASCADE"))
    __table_args__ = (UniqueConstraint("worker_id", "organization_id", "source_record_id"),)


class Review(UUIDTimestampMixin, Base):
    __tablename__ = "reviews"
    job_id: Mapped[UUID] = mapped_column(ForeignKey("jobs.id", ondelete="RESTRICT"), unique=True)
    reviewer_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    identity_verification_id: Mapped[UUID] = mapped_column(ForeignKey("identity_verifications.id", ondelete="RESTRICT"))
    rating: Mapped[int] = mapped_column(Integer)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(128))
    payload_hash: Mapped[str] = mapped_column(String(64))
    __table_args__ = (CheckConstraint("rating BETWEEN 1 AND 5", name="review_rating_range"),)
