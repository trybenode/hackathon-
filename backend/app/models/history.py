"""Worker declarations and respondent evidence, deliberately outside scored outcomes."""
from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base, UUIDTimestampMixin


class HistoryClaim(UUIDTimestampMixin, Base):
    __tablename__ = "history_claims"
    __table_args__ = (UniqueConstraint("worker_id", "operation_id", name="uq_history_claims_worker_operation"), UniqueConstraint("worker_id", "job_id", name="uq_history_claims_worker_job"), CheckConstraint("revision > 0", name="positive_revision"))
    worker_id: Mapped[UUID] = mapped_column(ForeignKey("workers.id", ondelete="RESTRICT"), index=True)
    job_id: Mapped[UUID | None] = mapped_column(ForeignKey("jobs.id", ondelete="RESTRICT"), nullable=True)
    operation_id: Mapped[UUID] = mapped_column()
    payload_hash: Mapped[str] = mapped_column(String(64))
    revision: Mapped[int] = mapped_column(Integer, default=1)
    details: Mapped[dict] = mapped_column(JSON)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ConfirmationRequest(UUIDTimestampMixin, Base):
    __tablename__ = "history_confirmation_requests"
    __table_args__ = (UniqueConstraint("claim_id", "operation_id"),)
    claim_id: Mapped[UUID] = mapped_column(ForeignKey("history_claims.id", ondelete="RESTRICT"), index=True)
    operation_id: Mapped[UUID] = mapped_column()
    payload_hash: Mapped[str] = mapped_column(String(64))
    revision: Mapped[int] = mapped_column(Integer)
    snapshot: Mapped[dict] = mapped_column(JSON)
    recipient_phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    hiring_customer_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    challenge_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    challenge_reference: Mapped[str | None] = mapped_column(String(160), nullable=True)
    challenge_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    challenge_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    challenge_send_count: Mapped[int] = mapped_column(Integer, default=0)
    challenge_attempts: Mapped[int] = mapped_column(Integer, default=0)
    challenge_sandbox: Mapped[bool] = mapped_column(Boolean, default=False)
    session_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    session_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CustomerResponse(UUIDTimestampMixin, Base):
    __tablename__ = "history_customer_responses"
    request_id: Mapped[UUID] = mapped_column(ForeignKey("history_confirmation_requests.id", ondelete="RESTRICT"), unique=True)
    actor_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=True)
    operation_id: Mapped[UUID] = mapped_column()
    payload_hash: Mapped[str] = mapped_column(String(64))
    decision: Mapped[str] = mapped_column(String(30))
    declares_customer: Mapped[bool] = mapped_column(Boolean, default=False)
    attribution: Mapped[str] = mapped_column(String(40))
    sandbox: Mapped[bool] = mapped_column(Boolean, default=False)
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class HistoryDraft(UUIDTimestampMixin, Base):
    __tablename__ = "history_drafts"
    __table_args__ = (UniqueConstraint("worker_id", "operation_id"),)
    worker_id: Mapped[UUID] = mapped_column(ForeignKey("workers.id", ondelete="RESTRICT"), index=True)
    job_id: Mapped[UUID | None] = mapped_column(ForeignKey("jobs.id", ondelete="RESTRICT"), nullable=True)
    operation_id: Mapped[UUID] = mapped_column()
    payload_hash: Mapped[str] = mapped_column(String(64))
    language: Mapped[str] = mapped_column(String(2))
    status: Mapped[str] = mapped_column(String(20), default="queued", index=True)
    audio_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    transcript: Mapped[str | None] = mapped_column(Text, nullable=True)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    model_metadata: Mapped[dict] = mapped_column(JSON, default=dict)
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    claim_id: Mapped[UUID | None] = mapped_column(ForeignKey("history_claims.id", ondelete="RESTRICT"), nullable=True)


class HistoryMessage(UUIDTimestampMixin, Base):
    __tablename__ = "history_messages"
    __table_args__ = (UniqueConstraint("request_id", "actor_role", "operation_id"),)
    request_id: Mapped[UUID] = mapped_column(ForeignKey("history_confirmation_requests.id", ondelete="RESTRICT"), index=True)
    actor_role: Mapped[str] = mapped_column(String(10))
    actor_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=True)
    operation_id: Mapped[UUID] = mapped_column()
    payload_hash: Mapped[str] = mapped_column(String(64))
    language: Mapped[str] = mapped_column(String(2))
    text: Mapped[str] = mapped_column(Text)


class MessageTranslation(UUIDTimestampMixin, Base):
    __tablename__ = "history_message_translations"
    __table_args__ = (UniqueConstraint("message_id", "target"),)
    message_id: Mapped[UUID] = mapped_column(ForeignKey("history_messages.id", ondelete="RESTRICT"))
    target: Mapped[str] = mapped_column(String(2))
    status: Mapped[str] = mapped_column(String(20))
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    model: Mapped[str] = mapped_column(String(80))
    model_revision: Mapped[str | None] = mapped_column(String(160), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)


class MessageAudio(UUIDTimestampMixin, Base):
    """Private derivative speech with a fenced durable processing lease."""
    __tablename__ = "history_message_audio"
    __table_args__ = (UniqueConstraint("translation_id", "fingerprint", name="uq_history_audio_translation_fingerprint"),)
    translation_id: Mapped[UUID] = mapped_column(ForeignKey("history_message_translations.id", ondelete="RESTRICT"))
    fingerprint: Mapped[str] = mapped_column(String(64))
    language: Mapped[str] = mapped_column(String(2))
    status: Mapped[str] = mapped_column(String(20), default="queued", index=True)
    provider_model: Mapped[str] = mapped_column(String(160))
    provider_version: Mapped[str] = mapped_column(String(160))
    audio_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
