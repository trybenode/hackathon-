"""Shared domain errors, ownership and audit helpers without record dependencies."""
from datetime import UTC, datetime
from hashlib import sha256
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.domain import AuditEvent, User, Worker


class FeatureError(Exception):
    """Expected domain failure with a stable HTTP-facing code."""
    def __init__(self, status: int, code: str, detail: str, retry_after: int | None = None) -> None:
        self.status, self.code, self.detail, self.retry_after = status, code, detail, retry_after
        super().__init__(detail)


def now() -> datetime:
    """Return the clock used by expiring grants and review windows."""
    return datetime.now(UTC)


def aware(value: datetime) -> datetime:
    """Normalize SQLite timestamps without changing Postgres timestamps."""
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def digest(value: str) -> str:
    """Hash random bearer credentials before persistence."""
    return sha256(value.encode()).hexdigest()


def audit(session: AsyncSession, actor_id: UUID | None, entity_type: str, entity_id: UUID, action: str, metadata: dict | None = None) -> None:
    """Record meaningful changes without bearer tokens or private comments."""
    session.add(AuditEvent(actor_id=actor_id, entity_type=entity_type, entity_id=entity_id, action=action, event_metadata=metadata or {}))


async def own_worker(session: AsyncSession, user: User) -> Worker:
    """Resolve an active user's worker record; never trust a caller's UUID."""
    worker = await session.scalar(select(Worker).where(Worker.user_id == user.id))
    if not user.is_active or worker is None:
        raise FeatureError(404, "WORKER_NOT_FOUND", "No worker record is linked to this account.")
    return worker


