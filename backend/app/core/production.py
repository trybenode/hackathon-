"""Validate deployment settings without exposing secrets; used by API and production launcher."""
import json
from urllib.parse import urlsplit
from app.core.config import Settings


def validate_production_settings(cfg: Settings) -> None:
    """Fail startup on unsafe non-development configuration; optional providers stay off."""
    if cfg.environment == 'development':
        return
    errors: list[str] = []
    if cfg.environment not in {'production', 'staging', 'test'}:
        errors.append('ENVIRONMENT')
    db = urlsplit(cfg.database_url)
    if db.scheme not in {'postgresql', 'postgresql+asyncpg'} or not db.hostname or 'placeholder' in cfg.database_url:
        errors.append('DATABASE_URL')
    if not cfg.redis_url.startswith(('redis://', 'rediss://')):
        errors.append('REDIS_URL')
    for name, value in [('CREDENTIAL_SIGNING_SECRET', cfg.credential_signing_secret), ('INTERNAL_PROXY_SECRET', cfg.internal_proxy_secret)]:
        if len(value.strip()) < 32 or '<' in value or value.lower().startswith(('change', 'replace', 'example')):
            errors.append(name)
    def https_origin(value: str) -> bool:
        parts = urlsplit(value)
        return parts.scheme == 'https' and bool(parts.hostname) and parts.hostname not in {'localhost', '127.0.0.1', '::1'} and parts.path in {'', '/'} and not parts.query and not parts.fragment and not parts.username
    if not https_origin(cfg.frontend_base_url):
        errors.append('FRONTEND_BASE_URL')
    if not cfg.cors_origin_list or any(not https_origin(origin) for origin in cfg.cors_origin_list) or cfg.frontend_base_url.rstrip('/') not in cfg.cors_origin_list:
        errors.append('CORS_ORIGINS')
    if not cfg.resend_api_key.strip() or 'onboarding@resend.dev' in cfg.resend_from or '@' not in cfg.resend_from:
        errors.append('RESEND_API_KEY/RESEND_FROM')
    if cfg.platform_api_key:
        errors.append('PLATFORM_API_KEY (development-only)')
    if cfg.sms_provider not in {'disabled', 'twilio'}:
        errors.append('SMS_PROVIDER')
    if cfg.sms_provider == 'twilio' and not all((cfg.twilio_account_sid, cfg.twilio_auth_token, cfg.twilio_verify_service_sid)):
        errors.append('TWILIO credentials')
    if cfg.escrow_enabled and (urlsplit(cfg.payscrow_base_url).hostname != 'api.payscrow.net' or not cfg.payscrow_base_url.startswith('https://') or len(cfg.payscrow_webhook_secret) < 32 or not cfg.payscrow_webhook_url.startswith('https://')):
        errors.append('PAYSCROW production endpoint/webhook')
    if cfg.history_ai_enabled and (not cfg.history_ai_base_url.startswith('https://') or not cfg.history_ai_api_key):
        errors.append('HISTORY_AI_BASE_URL/API_KEY')
    if cfg.history_speech_enabled:
        requested = {value.strip() for value in cfg.history_speech_languages.split(',') if value.strip()}
        reviewed = {value.strip() for value in cfg.history_speech_reviewed_languages.split(',') if value.strip()}
        valid = bool(cfg.history_speech_api_key and cfg.history_speech_model and cfg.history_speech_version)
        if cfg.history_speech_provider == 'spitch':
            try:
                voices = json.loads(cfg.history_speech_voices)
            except (ValueError, TypeError):
                voices = {}
            valid = valid and isinstance(voices, dict) and all(isinstance(voices.get(language), str) and voices[language].strip() for language in requested)
        elif cfg.history_speech_provider == 'gateway':
            valid = valid and cfg.history_speech_base_url.startswith('https://')
        else:
            valid = False
        if not valid or not requested or not requested <= {'en', 'yo', 'ha', 'ig'} or not requested <= reviewed:
            errors.append('HISTORY_SPEECH configuration/reviewed languages')
    if (cfg.history_ai_enabled or cfg.history_speech_enabled) and (not cfg.run_history_worker or not cfg.history_audio_dir):
        errors.append('RUN_HISTORY_WORKER/HISTORY_AUDIO_DIR')
    if errors:
        raise RuntimeError('Invalid production configuration: ' + ', '.join(errors))
