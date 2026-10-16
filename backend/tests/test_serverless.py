"""Protect serverless configuration, connection isolation and absence of background loops."""
from unittest.mock import AsyncMock
import pytest
from sqlalchemy.pool import NullPool
from app.core.config import Settings
from app.core.production import validate_production_settings


def serverless_settings(**overrides: object) -> Settings:
    """Construct a secret-free, isolated production demo configuration."""
    values = dict(environment="production", deployment_mode="serverless",
                  database_url="postgresql+asyncpg://test:test@localhost/test",
                  redis_url="rediss://test@localhost:6379", expiry_sweep_seconds=0,
                  credential_signing_secret="a"*64, internal_proxy_secret="b"*64,
                  frontend_base_url="https://app.example.com", cors_origins="https://app.example.com",
                  resend_api_key="mock-provider", resend_from="Trust <login@example.com>",
                  sms_provider="disabled")
    values.update(overrides)
    return Settings(_env_file=None, **{Settings.model_fields[key].alias or key: value
                                     for key, value in values.items()})


def test_serverless_configuration_and_detection(monkeypatch):
    validate_production_settings(serverless_settings())
    monkeypatch.setenv("VERCEL", "1")
    assert Settings(_env_file=None).deployment_mode == "serverless"


@pytest.mark.parametrize("change", [dict(run_history_worker=True), dict(history_ai_enabled=True),
                                  dict(history_speech_enabled=True), dict(expiry_sweep_seconds=900),
                                  dict(environment="development")])
def test_serverless_rejects_unsupported_execution(change):
    with pytest.raises(RuntimeError, match="[Ss]erverless"):
        validate_production_settings(serverless_settings(**change))


async def test_serverless_connections_are_not_pooled(monkeypatch):
    from app.db import session
    monkeypatch.setattr(session, "settings", serverless_settings())
    engine = session.create_application_engine()
    assert isinstance(engine.pool, NullPool)
    await engine.dispose()


async def test_serverless_lifespan_does_not_start_timer(monkeypatch):
    from app import main
    # Prove the runtime guard independently of the required zero interval config.
    cfg = serverless_settings(expiry_sweep_seconds=900)
    monkeypatch.setattr(main, "settings", cfg)
    monkeypatch.setattr(main, "validate_production_settings", lambda _: None)
    sweep = AsyncMock()
    monkeypatch.setattr(main, "sweep_forever", sweep)
    async with main.lifespan(main.app):
        pass
    sweep.assert_not_called()


def test_serverless_allows_private_external_voice_worker():
    validate_production_settings(serverless_settings(history_ai_enabled=True,
        history_external_worker=True, history_audio_storage="s3", history_audio_bucket="private-audio",
        history_ai_base_url="https://models.example.com", history_ai_api_key="key-"*16))


@pytest.mark.parametrize("change", [dict(history_audio_storage="local"), dict(history_audio_bucket="")])
def test_external_worker_requires_private_storage(change):
    values = dict(history_ai_enabled=True, history_external_worker=True,
                  history_audio_storage="s3", history_audio_bucket="private-audio",
                  history_ai_base_url="https://models.example.com", history_ai_api_key="key-"*16)
    values.update(change)
    with pytest.raises(RuntimeError):
        validate_production_settings(serverless_settings(**values))
