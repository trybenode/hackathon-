"""Configured private speech gateway; serves translated-message jobs, never account authentication."""
import json
from dataclasses import dataclass
from typing import Protocol
import httpx
from app.core.config import get_settings
from app.services.feature_common import FeatureError

MAX_AUDIO_BYTES = 5 * 1024 * 1024


@dataclass(frozen=True)
class SpeechResult:
    """Validated MP3 bytes and actual provider model identity."""
    audio: bytes
    model: str
    version: str


class SpeechProvider(Protocol):
    """Synthesize exact translated text in a validated language."""
    async def synthesize(self, text: str, language: str) -> SpeechResult: ...


def supported_languages() -> list[str]:
    """Return only configured, explicitly validated languages; disabled by default."""
    cfg = get_settings()
    if not (cfg.history_speech_enabled and cfg.history_speech_model and cfg.history_speech_version and cfg.history_speech_api_key):
        return []
    languages = {value.strip() for value in cfg.history_speech_languages.split(',')} & {'en', 'yo', 'ha', 'ig'}
    if cfg.history_speech_provider == 'spitch':
        return sorted(languages & voice_mapping().keys())
    if cfg.history_speech_provider != 'gateway' or not cfg.history_speech_base_url:
        return []
    if cfg.environment != 'development' and not cfg.history_speech_base_url.startswith('https://'):
        return []
    return sorted(languages)


def voice_mapping() -> dict[str, str]:
    """Read explicit language-to-voice JSON; malformed configuration disables voices."""
    try:
        values = json.loads(get_settings().history_speech_voices)
    except (ValueError, TypeError):
        return {}
    if not isinstance(values, dict):
        return {}
    return {language: voice.strip() for language, voice in values.items()
            if language in {'en', 'yo', 'ha', 'ig'} and isinstance(voice, str) and voice.strip()}


def configuration_identity(language: str) -> str:
    """Invalidate queued/cached audio after a provider, revision or voice change."""
    cfg = get_settings()
    voice = voice_mapping().get(language, '') if cfg.history_speech_provider == 'spitch' else ''
    return json.dumps([cfg.history_speech_provider, cfg.history_speech_base_url,
                       cfg.history_speech_model, cfg.history_speech_version, voice])


class GatewaySpeechProvider:
    """Call an authenticated provider adapter; reject mismatched language/model responses."""
    async def synthesize(self, text: str, language: str) -> SpeechResult:
        cfg = get_settings()
        if language not in supported_languages():
            raise FeatureError(503, 'SPEECH_UNAVAILABLE', 'Audio is unavailable for this language.')
        if cfg.environment != 'development' and not cfg.history_speech_base_url.startswith('https://'):
            raise FeatureError(503, 'SPEECH_UNAVAILABLE', 'Speech gateway requires HTTPS.')
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                async with client.stream('POST', cfg.history_speech_base_url.rstrip('/') + '/synthesize', headers={'Authorization': f'Bearer {cfg.history_speech_api_key}'}, json={'text': text, 'language': language, 'model': cfg.history_speech_model, 'version': cfg.history_speech_version}) as response:
                    response.raise_for_status()
                    if response.headers.get('content-type', '').split(';')[0] != 'audio/mpeg' or response.headers.get('x-speech-language') != language or response.headers.get('x-speech-model') != cfg.history_speech_model or response.headers.get('x-speech-version') != cfg.history_speech_version:
                        raise FeatureError(503, 'SPEECH_INVALID_RESPONSE', 'Speech response could not be validated.')
                    chunks = bytearray()
                    async for chunk in response.aiter_bytes():
                        chunks.extend(chunk)
                        if len(chunks) > MAX_AUDIO_BYTES:
                            raise FeatureError(503, 'SPEECH_INVALID_RESPONSE', 'Speech response exceeds the audio limit.')
            audio = bytes(chunks)
            if not (audio.startswith(b'ID3') or len(audio) >= 2 and audio[0] == 255 and audio[1] & 224 == 224):
                raise FeatureError(503, 'SPEECH_INVALID_RESPONSE', 'Speech response is not MP3 audio.')
            return SpeechResult(audio, cfg.history_speech_model, cfg.history_speech_version)
        except httpx.HTTPError as error:
            raise FeatureError(503, 'SPEECH_PROVIDER_FAILED', 'Audio generation failed. Retry later.') from error


class SpitchSpeechProvider:
    """Request exact translated text as MP3 from Spitch using an explicit voice."""
    async def synthesize(self, text: str, language: str) -> SpeechResult:
        cfg = get_settings()
        if cfg.history_speech_provider != 'spitch' or language not in supported_languages():
            raise FeatureError(503, 'SPEECH_UNAVAILABLE', 'Audio is unavailable for this language.')
        try:
            async with httpx.AsyncClient(timeout=60, follow_redirects=False) as client:
                async with client.stream(
                    'POST', 'https://api.spitch.app/v1/speech',
                    headers={'Authorization': f'Bearer {cfg.history_speech_api_key}'},
                    json={'text': text, 'language': language,
                          'voice': voice_mapping()[language], 'format': 'mp3'},
                ) as response:
                    response.raise_for_status()
                    if response.headers.get('content-type', '').split(';')[0].strip() != 'audio/mpeg':
                        raise FeatureError(503, 'SPEECH_INVALID_RESPONSE', 'Speech response is not MP3 audio.')
                    chunks = bytearray()
                    async for chunk in response.aiter_bytes():
                        chunks.extend(chunk)
                        if len(chunks) > MAX_AUDIO_BYTES:
                            raise FeatureError(503, 'SPEECH_INVALID_RESPONSE', 'Speech response exceeds the audio limit.')
            audio = bytes(chunks)
            if not (audio.startswith(b'ID3') or len(audio) >= 2 and audio[0] == 255 and audio[1] & 224 == 224):
                raise FeatureError(503, 'SPEECH_INVALID_RESPONSE', 'Speech response is not MP3 audio.')
            return SpeechResult(audio, cfg.history_speech_model, cfg.history_speech_version)
        except httpx.HTTPError as error:
            raise FeatureError(503, 'SPEECH_PROVIDER_FAILED', 'Audio generation failed. Retry later.') from error


class ConfiguredSpeechProvider:
    """Select the configured adapter without changing worker or route dependencies."""
    async def synthesize(self, text: str, language: str) -> SpeechResult:
        provider = SpitchSpeechProvider() if get_settings().history_speech_provider == 'spitch' else GatewaySpeechProvider()
        return await provider.synthesize(text, language)


speech_provider: SpeechProvider = ConfiguredSpeechProvider()
