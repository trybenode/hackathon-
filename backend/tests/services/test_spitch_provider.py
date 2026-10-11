"""Validate the Spitch adapter without paid requests or real credentials; serves speech regressions."""
import json
import httpx
import pytest
from app.core.config import get_settings
from app.services import speech_provider, history_speech
from app.services.feature_common import FeatureError


@pytest.fixture
def spitch(monkeypatch):
    cfg = get_settings()
    for key, value in {'history_speech_provider': 'spitch', 'history_speech_enabled': True, 'history_speech_api_key': 'test', 'history_speech_model': 'managed', 'history_speech_version': 'config-1', 'history_speech_languages': 'en,yo,ha,ig', 'history_speech_voices': '{"en":"john","yo":"sade","ha":"amina","ig":"ngozi"}'}.items():
        monkeypatch.setattr(cfg, key, value)
    return cfg


@pytest.mark.parametrize('language,voice', [('en','john'), ('yo','sade'), ('ha','amina'), ('ig','ngozi')])
async def test_exact_translation(spitch, monkeypatch, language, voice):
    real_client = httpx.AsyncClient
    def handle(request):
        assert str(request.url) == 'https://api.spitch.app/v1/speech'
        assert request.headers['authorization'] == 'Bearer test'
        assert json.loads(request.content) == {'text': 'Not paid ₦25,000', 'language': language, 'voice': voice, 'format': 'mp3'}
        return httpx.Response(200, headers={'Content-Type':'audio/mpeg'}, content=b'ID3test')
    monkeypatch.setattr(httpx, 'AsyncClient', lambda **kwargs: real_client(transport=httpx.MockTransport(handle), **kwargs))
    assert (await speech_provider.speech_provider.synthesize('Not paid ₦25,000', language)).audio == b'ID3test'


@pytest.mark.parametrize('voices', ['', '[]', '{broken', '{"yo":""}', '{"yo":123}'])
async def test_missing_voice(spitch, monkeypatch, voices):
    monkeypatch.setattr(spitch, 'history_speech_voices', voices)
    assert speech_provider.supported_languages() == []
    with pytest.raises(FeatureError) as error:
        await speech_provider.speech_provider.synthesize('Ẹ ṣé', 'yo')
    assert error.value.code == 'SPEECH_UNAVAILABLE'


@pytest.mark.parametrize('status,kind,body,code', [(401,'application/json',b'{}','SPEECH_PROVIDER_FAILED'), (200,'audio/wav',b'RIFF','SPEECH_INVALID_RESPONSE'), (200,'audio/mpeg',b'garbage','SPEECH_INVALID_RESPONSE'), (200,'audio/mpeg',b'ID3'+b'x'*speech_provider.MAX_AUDIO_BYTES,'SPEECH_INVALID_RESPONSE')])
async def test_invalid_response(spitch, monkeypatch, status, kind, body, code):
    real_client = httpx.AsyncClient
    monkeypatch.setattr(httpx, 'AsyncClient', lambda **kwargs: real_client(transport=httpx.MockTransport(lambda request: httpx.Response(status, headers={'Content-Type':kind}, content=body)), **kwargs))
    with pytest.raises(FeatureError) as error:
        await speech_provider.speech_provider.synthesize('Ẹ ṣé','yo')
    assert error.value.code == code


def test_voice_and_configuration_change_fingerprint(spitch, monkeypatch):
    from app.models.history import MessageTranslation
    tr = MessageTranslation(target='yo', text='Ẹ ṣé', model='N-ATLAS', model_revision='1')
    first = history_speech.fingerprint(tr)
    monkeypatch.setattr(spitch, 'history_speech_voices', '{"yo":"femi"}')
    assert history_speech.fingerprint(tr) != first
    second = history_speech.fingerprint(tr)
    monkeypatch.setattr(spitch, 'history_speech_version', 'config-2')
    assert history_speech.fingerprint(tr) != second
