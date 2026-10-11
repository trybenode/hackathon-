"""Private translated speech queue; used by history routes and the durable history worker."""
import asyncio
from datetime import timedelta
from pathlib import Path
from uuid import UUID
from sqlalchemy import select, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from app.core.config import get_settings
from app.models.domain import Job
from app.models.history import MessageAudio, MessageTranslation, HistoryMessage, ConfirmationRequest, HistoryClaim
from app.schemas.history import AudioView
from app.services.feature_common import FeatureError, aware, digest, now, audit
from app.services.history_drafts import _write_audio, delete_audio, spool
from app.services import speech_provider


def fingerprint(translation: MessageTranslation) -> str:
    """Bind speech to exact translated text and translation model/version."""
    return digest(f'{translation.target}\0{translation.model}\0{translation.model_revision}\0{translation.text}\0{speech_provider.configuration_identity(translation.target)}')


def view(row: MessageAudio) -> AudioView:
    """Expose status and provenance without private paths."""
    return AudioView(id=row.id, language=row.language, status=row.status, model=row.provider_model, version=row.provider_version, expires_at=row.expires_at, error_code=row.error_code)


async def translation_for(session: AsyncSession, request_id: UUID, message_id: UUID, target: str) -> MessageTranslation:
    """Scope a ready translation to the caller's already-authorized thread."""
    row = await session.scalar(select(MessageTranslation).join(HistoryMessage, HistoryMessage.id == MessageTranslation.message_id).where(HistoryMessage.request_id == request_id, HistoryMessage.id == message_id, MessageTranslation.target == target))
    if row is None or row.status != 'ready' or not row.text:
        raise FeatureError(409, 'TRANSLATION_REQUIRED', 'Translate this message successfully before requesting audio.')
    return row


async def enqueue(session: AsyncSession, request_id: UUID, message_id: UUID, target: str, actor_id: UUID | None) -> AudioView:
    """Serialize on the translation to deduplicate concurrent speech requests."""
    tr = await translation_for(session, request_id, message_id, target)
    await session.execute(select(MessageTranslation.id).where(MessageTranslation.id == tr.id).with_for_update())
    row = await session.scalar(select(MessageAudio).where(MessageAudio.translation_id == tr.id, MessageAudio.fingerprint == fingerprint(tr)).with_for_update())
    if row and aware(row.expires_at) > now() and row.status != 'failed':
        return view(row)
    if target not in speech_provider.supported_languages():
        raise FeatureError(503, 'SPEECH_UNAVAILABLE', 'Audio is unavailable for this language.')
    cfg = get_settings()
    if row is None:
        row = MessageAudio(translation_id=tr.id, fingerprint=fingerprint(tr), language=target, provider_model=cfg.history_speech_model, provider_version=cfg.history_speech_version, expires_at=now()+timedelta(hours=24))
        session.add(row)
    else:
        await delete_audio(row.audio_path)
        row.audio_path = None; row.status = 'queued'; row.error_code = None; row.attempts = 0; row.lease_until = None
        row.expires_at = now()+timedelta(hours=24)
        row.provider_model = cfg.history_speech_model; row.provider_version = cfg.history_speech_version
    await session.flush()
    audit(session, actor_id, 'history_message_audio', row.id, 'requested', {'language': target})
    return view(row)


async def authorized_audio(session: AsyncSession, request_id: UUID, message_id: UUID, audio_id: UUID) -> MessageAudio:
    """Check exact message and current translation on every status/content retrieval."""
    row = await session.scalar(select(MessageAudio).join(MessageTranslation, MessageTranslation.id == MessageAudio.translation_id).join(HistoryMessage, HistoryMessage.id == MessageTranslation.message_id).where(MessageAudio.id == audio_id, HistoryMessage.id == message_id, HistoryMessage.request_id == request_id))
    if row is None:
        raise FeatureError(404, 'AUDIO_NOT_FOUND', 'Audio not found in this thread.')
    tr = await session.get(MessageTranslation, row.translation_id)
    if aware(row.expires_at) <= now() or tr.status != 'ready' or row.fingerprint != fingerprint(tr):
        await delete_audio(row.audio_path)
        row.audio_path = None; row.status = 'expired'; row.lease_until = None
    return row


async def content(row: MessageAudio) -> bytes:
    """Read only generated files in the private spool; never expose a filesystem path."""
    if row.status != 'ready' or not row.audio_path:
        raise FeatureError(409, 'AUDIO_NOT_READY', 'Audio is not ready or has expired.')
    path = Path(row.audio_path)
    if path.is_symlink() or path.parent.resolve() != spool().resolve():
        raise FeatureError(503, 'AUDIO_STORAGE_UNAVAILABLE', 'Private audio storage is unavailable.')
    try:
        return await asyncio.to_thread(path.read_bytes)
    except OSError as error:
        raise FeatureError(410, 'AUDIO_UNAVAILABLE', 'Audio is no longer available. Generate it again.') from error


async def live_request(session: AsyncSession, request: ConfirmationRequest, claim: HistoryClaim) -> bool:
    """Check snapshot and authoritative native-job attribution before and after inference."""
    if request.revoked_at or aware(request.expires_at) <= now() or claim.archived_at or claim.revision != request.revision:
        return False
    if claim.job_id:
        job = await session.get(Job, claim.job_id, populate_existing=True)
        return bool(job and job.worker_id == claim.worker_id and job.client_id and job.client_id == request.hiring_customer_id)
    return True


async def process_one(factory: async_sessionmaker[AsyncSession]) -> bool:
    """Lease a queued task, synthesize asynchronously, then fence and recheck authorization."""
    async with factory() as session:
        expired = (await session.scalars(select(MessageAudio).where(MessageAudio.expires_at <= now(), MessageAudio.status != 'expired').with_for_update(skip_locked=True).limit(100))).all()
        for row in expired:
            await delete_audio(row.audio_path)
            row.audio_path = None; row.status = 'expired'; row.lease_until = None
        row = await session.scalar(select(MessageAudio).where(MessageAudio.expires_at > now(), or_(MessageAudio.status == 'queued', and_(MessageAudio.status == 'processing', MessageAudio.lease_until < now()))).order_by(MessageAudio.created_at).with_for_update(skip_locked=True).limit(1))
        if row is None:
            await session.commit(); return False
        if row.attempts >= 3:
            row.status = 'failed'; row.error_code = 'SPEECH_ATTEMPTS_EXHAUSTED'
            await session.commit(); return True
        row.status = 'processing'; row.attempts += 1; row.lease_until = now()+timedelta(seconds=90)
        identity, attempt, lease = row.id, row.attempts, row.lease_until
        tr = await session.get(MessageTranslation, row.translation_id)
        msg = await session.get(HistoryMessage, tr.message_id)
        request = await session.get(ConfirmationRequest, msg.request_id)
        claim = await session.get(HistoryClaim, request.claim_id)
        if tr.status != 'ready' or not tr.text or row.fingerprint != fingerprint(tr) or not await live_request(session, request, claim):
            row.status = 'expired'; row.lease_until = None
            await session.commit(); return True
        text, language = tr.text, row.language
        await session.commit()
    path = None; result = None; error_code = None
    try:
        result = await speech_provider.speech_provider.synthesize(text, language)
        path = str(await asyncio.to_thread(_write_audio, result.audio))
    except FeatureError as error:
        error_code = error.code
    except Exception:
        error_code = 'SPEECH_PROCESSING_FAILED'
    async with factory() as session:
        row = await session.get(MessageAudio, identity, with_for_update=True)
        tr = await session.get(MessageTranslation, row.translation_id)
        msg = await session.get(HistoryMessage, tr.message_id)
        request = await session.get(ConfirmationRequest, msg.request_id)
        claim = await session.get(HistoryClaim, request.claim_id)
        valid = row.status == 'processing' and row.attempts == attempt and row.lease_until is not None and aware(row.lease_until) == aware(lease) and aware(row.expires_at) > now() and await live_request(session, request, claim) and tr.status == 'ready' and row.fingerprint == fingerprint(tr)
        if not valid:
            await delete_audio(path)
            if row.attempts == attempt and row.status == 'processing' and row.lease_until is not None and aware(row.lease_until) == aware(lease):
                row.status = 'expired'; row.lease_until = None
        elif result and result.model == row.provider_model and result.version == row.provider_version:
            row.audio_path = path; row.status = 'ready'; row.lease_until = None
        else:
            await delete_audio(path)
            row.status = 'failed'; row.error_code = error_code or 'SPEECH_MODEL_CHANGED'; row.lease_until = None
        await session.commit()
    return True
