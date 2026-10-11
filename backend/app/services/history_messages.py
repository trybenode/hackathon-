"""Immutable private clarification and separately labelled translations."""
from math import ceil
from uuid import UUID
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from app.models.history import HistoryClaim, ConfirmationRequest, HistoryMessage, MessageTranslation
from app.models.domain import User
from app.schemas.history import MessageCreate, MessageView, MessagePage, TranslationView, Language
from app.services.history_ai import HistoryModelGateway, LLM_MODEL
from app.services import history
from app.services.feature_common import FeatureError, audit, digest, now, aware


async def owner_thread(session: AsyncSession, user: User, claim_id: UUID, *, lock: bool = False) -> ConfirmationRequest:
    """Bind worker communication to the current active confirmation snapshot."""
    claim = await history.owned_claim(session, user, claim_id, lock=lock)
    row = await session.scalar(select(ConfirmationRequest).where(ConfirmationRequest.claim_id == claim.id, ConfirmationRequest.revision == claim.revision, ConfirmationRequest.revoked_at.is_(None), ConfirmationRequest.expires_at > now()).order_by(ConfirmationRequest.created_at.desc()).limit(1))
    if claim.archived_at or row is None:
        raise FeatureError(409, "THREAD_UNAVAILABLE", "Create a current confirmation request before clarifying this job.")
    return row


def translation_view(row: MessageTranslation) -> TranslationView:
    """A translation is a derivative, never verification evidence."""
    return TranslationView(target=row.target, status=row.status, text=row.text, model=row.model, model_revision=row.model_revision, error_code=row.error_code)


async def message_view(session: AsyncSession, row: HistoryMessage) -> MessageView:
    """Keep original text and all derivatives distinct."""
    translations = (await session.scalars(select(MessageTranslation).where(MessageTranslation.message_id == row.id))).all()
    return MessageView(id=row.id, operation_id=row.operation_id, actor_role=row.actor_role, language=row.language, text=row.text, created_at=row.created_at, translations=[translation_view(t) for t in translations])


async def messages(session: AsyncSession, request_id: UUID, page: int, size: int) -> MessagePage:
    """Paginate originals only after the caller has authorized the exact request."""
    total = await session.scalar(select(func.count()).select_from(HistoryMessage).where(HistoryMessage.request_id == request_id)) or 0
    rows = (await session.scalars(select(HistoryMessage).where(HistoryMessage.request_id == request_id).order_by(HistoryMessage.created_at.desc(), HistoryMessage.id).offset((page-1)*size).limit(size))).all()
    return MessagePage(items=[await message_view(session, row) for row in rows], total=total, page=page, size=size, pages=ceil(total/size))


async def send(session: AsyncSession, row: ConfirmationRequest, role: str, actor_id: UUID | None, payload: MessageCreate, operation: UUID) -> MessageView:
    """One operation yields one message; caller holds the claim serialization lock."""
    fingerprint = digest(payload.model_dump_json())
    previous = await session.scalar(select(HistoryMessage).where(HistoryMessage.request_id == row.id, HistoryMessage.actor_role == role, HistoryMessage.operation_id == operation))
    if previous:
        if previous.payload_hash != fingerprint:
            raise FeatureError(409, "IDEMPOTENCY_CONFLICT", "This operation was used with another message.")
        return await message_view(session, previous)
    message = HistoryMessage(request_id=row.id, actor_role=role, actor_id=actor_id, operation_id=operation, payload_hash=fingerprint, language=payload.language, text=payload.text)
    session.add(message); await session.flush()
    audit(session, actor_id, "history_message", message.id, "sent", {"role": role})
    return await message_view(session, message)


async def translate_message(session: AsyncSession, request_id: UUID, message_id: UUID, target: Language) -> TranslationView:
    """Translate only messages belonging to an authorized thread, preserving originals."""
    message = await session.scalar(select(HistoryMessage).where(HistoryMessage.id == message_id, HistoryMessage.request_id == request_id))
    if message is None:
        raise FeatureError(404, "MESSAGE_NOT_FOUND", "Message not found in this job.")
    query = select(MessageTranslation).where(MessageTranslation.message_id == message.id, MessageTranslation.target == target)
    row = await session.scalar(query.with_for_update())
    if row and row.status == "ready":
        return translation_view(row)
    if row is None:
        try:
            async with session.begin_nested():
                row = MessageTranslation(message_id=message.id, target=target, status="processing", model=LLM_MODEL)
                session.add(row); await session.flush()
        except IntegrityError:
            row = await session.scalar(query.with_for_update())
            if row.status == "ready":
                return translation_view(row)
    try:
        gateway = HistoryModelGateway()
        row.text = await gateway.translate(message.text, message.language, target)
        row.model_revision = gateway.translation_revision
        row.status = "ready"; row.error_code = None
    except FeatureError as error:
        row.text = None; row.status = "failed"; row.error_code = error.code
    # An owner may revoke while inference is in flight; don't return derivative after revoke.
    request = await session.get(ConfirmationRequest, request_id, populate_existing=True)
    claim = await session.get(HistoryClaim, request.claim_id, populate_existing=True)
    if request.revoked_at or aware(request.expires_at) <= now() or claim.archived_at or claim.revision != request.revision:
        raise FeatureError(410, "LINK_UNAVAILABLE", "This thread is no longer available.")
    return translation_view(row)
