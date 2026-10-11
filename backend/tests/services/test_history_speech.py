"""Speech stays derivative, private, deduplicated and bound to a current translation."""
from datetime import timedelta
from uuid import uuid4
import pytest
from sqlalchemy import select
from app.core.config import get_settings
from app.models.history import HistoryMessage, MessageTranslation, MessageAudio
from app.models.domain import User
from app.schemas.history import ClaimCreate, ClaimDetails, RequestCreate
from app.services import history, history_speech, speech_provider
from app.services.feature_common import FeatureError, now


@pytest.fixture
async def speech_context(session, worker, monkeypatch, tmp_path):
    cfg = get_settings()
    for name, value in {'history_speech_enabled': True, 'history_speech_base_url': 'http://localhost:9001', 'history_speech_api_key': 'test', 'history_speech_model': 'test-model', 'history_speech_version': 'v1', 'history_speech_languages': 'yo', 'history_audio_dir': str(tmp_path)}.items():
        monkeypatch.setattr(cfg, name, value)
    user = await session.get(User, worker.user_id)
    claim = await history.create_claim(session, user, ClaimCreate(details=ClaimDetails(work_type='Plumbing', description='Fixed pipe', language='en')), uuid4())
    request = await history.issue_request(session, user, claim.id, RequestCreate(revision=1, recipient_phone='+2348012345678'), uuid4())
    message = HistoryMessage(request_id=request.id, actor_role='customer', operation_id=uuid4(), payload_hash='test', language='en', text='Thank you')
    session.add(message); await session.flush()
    tr = MessageTranslation(message_id=message.id, target='yo', status='ready', text='Ẹ ṣé', model='N-ATLAS', model_revision='test')
    session.add(tr); await session.commit()
    return user, request, message, tr


async def test_speech_deduplicates_and_excludes_paths(session, speech_context):
    user, request, message, tr = speech_context
    first = await history_speech.enqueue(session, request.id, message.id, 'yo', user.id)
    second = await history_speech.enqueue(session, request.id, message.id, 'yo', user.id)
    assert first.id == second.id
    assert first.status == 'queued'
    assert 'audio_path' not in first.model_dump()
    assert len((await session.scalars(select(MessageAudio))).all()) == 1


async def test_speech_requires_ready_translation_and_supported_language(session, speech_context):
    user, request, message, tr = speech_context
    with pytest.raises(FeatureError) as absent:
        await history_speech.enqueue(session, request.id, message.id, 'ig', user.id)
    assert absent.value.code == 'TRANSLATION_REQUIRED'
    tr.target = 'ig'
    with pytest.raises(FeatureError) as unavailable:
        await history_speech.enqueue(session, request.id, message.id, 'ig', user.id)
    assert unavailable.value.code == 'SPEECH_UNAVAILABLE'


async def test_audio_expiry_and_changed_translation_block_playback(session, speech_context):
    user, request, message, tr = speech_context
    result = await history_speech.enqueue(session, request.id, message.id, 'yo', user.id)
    row = await session.get(MessageAudio, result.id)
    row.status = 'ready'; row.expires_at = now()-timedelta(seconds=1)
    checked = await history_speech.authorized_audio(session, request.id, message.id, row.id)
    assert checked.status == 'expired'
    with pytest.raises(FeatureError):
        await history_speech.content(checked)
    row.status = 'ready'; row.expires_at = now()+timedelta(hours=1)
    tr.text = 'Changed text'
    assert (await history_speech.authorized_audio(session, request.id, message.id, row.id)).status == 'expired'
    with pytest.raises(FeatureError) as wrong_thread:
        await history_speech.authorized_audio(session, uuid4(), message.id, row.id)
    assert wrong_thread.value.code == 'AUDIO_NOT_FOUND'


async def test_no_speech_capabilities_without_configuration(monkeypatch):
    monkeypatch.setattr(get_settings(), 'history_speech_enabled', False)
    assert speech_provider.supported_languages() == []


async def test_durable_generation_and_expiry_sweep(session, speech_context, monkeypatch):
    from sqlalchemy.ext.asyncio import async_sessionmaker
    from app.services.speech_provider import SpeechResult
    user, request, message, tr = speech_context
    class Provider:
        async def synthesize(self, text, language):
            assert text == 'Ẹ ṣé'
            assert language == 'yo'
            return SpeechResult(b'ID3test-mp3', 'test-model', 'v1')
    monkeypatch.setattr(speech_provider, 'speech_provider', Provider())
    result = await history_speech.enqueue(session, request.id, message.id, 'yo', user.id)
    await session.commit()
    factory = async_sessionmaker(session.bind, expire_on_commit=False)
    assert await history_speech.process_one(factory)
    row = await session.get(MessageAudio, result.id, populate_existing=True)
    assert row.status == 'ready'
    assert await history_speech.content(row) == b'ID3test-mp3'
    from pathlib import Path
    path = Path(row.audio_path)
    row.expires_at = now()-timedelta(seconds=1)
    await session.commit()
    await history_speech.process_one(factory)
    assert not path.exists()
    row = await session.get(MessageAudio, result.id, populate_existing=True)
    assert row.status == 'expired'


async def test_provider_failure_and_revocation_do_not_publish_audio(session, speech_context, monkeypatch):
    from sqlalchemy.ext.asyncio import async_sessionmaker
    from app.models.history import ConfirmationRequest
    user, request, message, tr = speech_context
    class Provider:
        async def synthesize(self, text, language):
            raise FeatureError(503, 'SPEECH_PROVIDER_FAILED', 'Failed')
    monkeypatch.setattr(speech_provider, 'speech_provider', Provider())
    result = await history_speech.enqueue(session, request.id, message.id, 'yo', user.id)
    await session.commit()
    factory = async_sessionmaker(session.bind, expire_on_commit=False)
    await history_speech.process_one(factory)
    row = await session.get(MessageAudio, result.id, populate_existing=True)
    assert row.status == 'failed'
    assert row.error_code == 'SPEECH_PROVIDER_FAILED'
    await history_speech.enqueue(session, request.id, message.id, 'yo', user.id)
    req = await session.get(ConfirmationRequest, request.id)
    req.revoked_at = now()
    await session.commit()
    await history_speech.process_one(factory)
    row = await session.get(MessageAudio, result.id, populate_existing=True)
    assert row.status == 'expired'
    assert row.audio_path is None


async def test_concurrent_speech_requests_share_one_task(session, speech_context):
    import asyncio
    from sqlalchemy.ext.asyncio import async_sessionmaker
    if session.bind.dialect.name != 'postgresql':
        pytest.skip('PostgreSQL row locking required')
    user, request, message, tr = speech_context
    factory = async_sessionmaker(session.bind, expire_on_commit=False)
    async def create():
        async with factory() as writer:
            result = await history_speech.enqueue(writer, request.id, message.id, 'yo', user.id)
            await writer.commit()
            return result.id
    first, second = await asyncio.gather(create(), create())
    assert first == second
    assert len((await session.scalars(select(MessageAudio))).all()) == 1


async def test_speech_gateway_rejects_wrong_language_and_accepts_exact_model(speech_context, monkeypatch):
    import httpx
    from app.services.speech_provider import GatewaySpeechProvider
    real_client = httpx.AsyncClient
    headers = {'Content-Type': 'audio/mpeg', 'X-Speech-Language': 'yo', 'X-Speech-Model': 'test-model', 'X-Speech-Version': 'v1'}
    def handle(request):
        assert request.headers['authorization'] == 'Bearer test'
        return httpx.Response(200, headers=headers, content=b'ID3test')
    monkeypatch.setattr(httpx, 'AsyncClient', lambda **kwargs: real_client(transport=httpx.MockTransport(handle), **kwargs))
    result = await GatewaySpeechProvider().synthesize('Ẹ ṣé', 'yo')
    assert result.audio == b'ID3test'
    headers['X-Speech-Language'] = 'en'
    with pytest.raises(FeatureError) as error:
        await GatewaySpeechProvider().synthesize('Ẹ ṣé', 'yo')
    assert error.value.code == 'SPEECH_INVALID_RESPONSE'


async def test_spitch_voice_change_requeues_and_expires_old_audio(session, speech_context, monkeypatch):
    cfg = get_settings()
    monkeypatch.setattr(cfg, 'history_speech_provider', 'spitch')
    monkeypatch.setattr(cfg, 'history_speech_voices', '{"yo":"sade"}')
    user, request, message, tr = speech_context
    first = await history_speech.enqueue(session, request.id, message.id, 'yo', user.id)
    monkeypatch.setattr(cfg, 'history_speech_voices', '{"yo":"femi"}')
    second = await history_speech.enqueue(session, request.id, message.id, 'yo', user.id)
    assert first.id != second.id
    assert second.status == 'queued'
    old = await history_speech.authorized_audio(session, request.id, message.id, first.id)
    assert old.status == 'expired'
