"""Production config and private proxy guards; no real providers or deployment resources used."""
import os
import time
import pytest
from fastapi import FastAPI, Request
from httpx import ASGITransport, AsyncClient
from app.core.config import Settings, get_settings
from app.core.production import validate_production_settings
from app.core.production_http import ProductionProxyMiddleware
from app.services.feature_common import FeatureError


def production_settings(**overrides) -> Settings:
    """Create isolated explicit configuration; never consume workstation dotenv secrets."""
    values = dict(environment='production', database_url='postgresql://user:secret@db.example.com/trust?sslmode=require', redis_url='redis://redis:6379/0', credential_signing_secret='a'*48, internal_proxy_secret='b'*48, frontend_base_url='https://app.example.com', cors_origins='https://app.example.com', resend_api_key='provider-test', resend_from='Trust <login@example.com>', sms_provider='disabled')
    values.update(overrides)
    return Settings(_env_file=None, **{Settings.model_fields[key].alias or key: value for key, value in values.items()})


def test_valid_configuration():
    validate_production_settings(production_settings())


@pytest.mark.parametrize('changes,field', [
    ({'environment':'prodction'}, 'ENVIRONMENT'),
    ({'database_url':'sqlite:///tmp.db'}, 'DATABASE_URL'),
    ({'redis_url':''}, 'REDIS_URL'),
    ({'credential_signing_secret':'short'}, 'CREDENTIAL_SIGNING_SECRET'),
    ({'internal_proxy_secret':'<generate-32-or-more-random-characters>'}, 'INTERNAL_PROXY_SECRET'),
    ({'frontend_base_url':'http://localhost:3000'}, 'FRONTEND_BASE_URL'),
    ({'cors_origins':'*'}, 'CORS_ORIGINS'),
    ({'resend_api_key':''}, 'RESEND_API_KEY'),
    ({'resend_from':'Trust <onboarding@resend.dev>'}, 'RESEND_FROM'),
    ({'platform_api_key':'legacy-secret'}, 'PLATFORM_API_KEY'),
    ({'sms_provider':'stub'}, 'SMS_PROVIDER'),
    ({'sms_provider':'twilio'}, 'TWILIO'),
    ({'payscrow_api_key':'test', 'payscrow_base_url':'https://api.payscrow.net.evil.example'}, 'PAYSCROW'),
    ({'history_ai_enabled':True}, 'HISTORY_AI'),
    ({'history_speech_enabled':True}, 'HISTORY_SPEECH'),
])
def test_invalid_configuration_names_fields_without_secrets(changes, field):
    with pytest.raises(RuntimeError) as error:
        validate_production_settings(production_settings(**changes))
    assert field in str(error.value)
    assert 'legacy-secret' not in str(error.value)
    assert 'postgresql://' not in str(error.value)


def test_spitch_requires_reviewed_voice_and_durable_worker():
    cfg = production_settings(history_speech_enabled=True, history_speech_provider='spitch', history_speech_api_key='test', history_speech_model='managed', history_speech_version='1', history_speech_voices='{"yo":"sade"}', history_speech_languages='yo', history_speech_reviewed_languages='yo', run_history_worker=True, history_audio_dir='/var/lib/trust/history')
    validate_production_settings(cfg)
    cfg.history_speech_reviewed_languages = ''
    with pytest.raises(RuntimeError, match='reviewed languages'):
        validate_production_settings(cfg)
    cfg.history_speech_reviewed_languages = 'yo'; cfg.run_history_worker = False
    with pytest.raises(RuntimeError, match='RUN_HISTORY_WORKER'):
        validate_production_settings(cfg)


async def test_production_stubs_do_not_verify_or_log(monkeypatch):
    from app.services.identity_provider import StubIdentityProvider, StubLivenessProvider, IdentitySubmission, LivenessSubmission
    from app.services.email_sender import LoggingEmailSender, EmailMessage, EmailDeliveryError
    from app.services.escrow_provider import StubEscrowProvider, EscrowProviderError
    monkeypatch.setattr(get_settings(), 'environment', 'production')
    with pytest.raises(FeatureError, match='not configured'):
        await StubIdentityProvider().verify(IdentitySubmission('A','B','phone','area','12345678901','12345678901'))
    with pytest.raises(FeatureError):
        await StubLivenessProvider().check(LivenessSubmission(b'x'*200))
    sender = LoggingEmailSender()
    with pytest.raises(EmailDeliveryError):
        await sender.send(EmailMessage('test@example.com','Code','secret code'))
    assert sender.sent == []
    with pytest.raises(EscrowProviderError):
        await StubEscrowProvider().status('STUB-123')


async def test_proxy_ip_requires_server_secret_and_origin(monkeypatch):
    cfg = get_settings()
    monkeypatch.setattr(cfg, 'environment', 'production')
    monkeypatch.setattr(cfg, 'internal_proxy_secret', 'b'*48)
    monkeypatch.setattr(cfg, 'cors_origins', 'https://app.example.com')
    app = FastAPI(); app.add_middleware(ProductionProxyMiddleware)
    @app.api_route('/probe', methods=['GET', 'POST'])
    async def probe(request: Request):
        return {'ip': request.client.host, 'key': request.headers.get('x-trust-proxy-key')}
    async with AsyncClient(transport=ASGITransport(app=app), base_url='https://test') as client:
        response = await client.get('/probe', headers={'X-Trust-Client-IP':'203.0.113.10','X-Trust-Proxy-Key':'wrong','X-Forwarded-For':'203.0.113.10'})
        assert response.json()['ip'] == '127.0.0.1'
        response = await client.get('/probe', headers={'X-Trust-Client-IP':'203.0.113.10','X-Trust-Proxy-Key':'b'*48})
        assert response.json() == {'ip':'203.0.113.10','key':None}
        rejected = await client.post('/probe', headers={'Cookie':'guarantor_session=test', 'Origin':'https://evil.example'})
        assert rejected.status_code == 403
        accepted = await client.post('/probe', headers={'Cookie':'guarantor_session=test','Origin':'https://app.example.com'})
        assert accepted.status_code == 200


async def test_readiness_fails_for_redis_and_stale_worker(monkeypatch, tmp_path):
    from redis.asyncio import Redis
    from redis.exceptions import RedisError
    from app.main import app
    from app.db.session import get_db_session
    class Session:
        async def execute(self, statement):
            return None
    async def db():
        yield Session()
    class Probe:
        failed = False
        async def __aenter__(self): return self
        async def __aexit__(self, *args): return None
        async def ping(self):
            if self.failed: raise RedisError('secret internal address')
            return True
    probe = Probe()
    monkeypatch.setattr(Redis, 'from_url', lambda *args, **kwargs: probe)
    cfg = get_settings(); monkeypatch.setattr(cfg, 'run_history_worker', False)
    app.dependency_overrides[get_db_session] = db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url='https://test') as client:
            assert (await client.get('/api/v1/health/live')).status_code == 200
            assert (await client.get('/api/v1/health/ready')).status_code == 200
            probe.failed = True
            response = await client.get('/api/v1/health/ready')
            assert response.status_code == 503 and 'secret internal' not in response.text
            probe.failed = False
            heartbeat = tmp_path / 'heartbeat'; heartbeat.touch(); os.utime(heartbeat, (time.time()-300, time.time()-300))
            monkeypatch.setattr(cfg, 'run_history_worker', True)
            monkeypatch.setattr(cfg, 'history_worker_heartbeat', str(heartbeat))
            assert (await client.get('/api/v1/health/ready')).status_code == 503
            heartbeat.touch()
            assert (await client.get('/api/v1/health/ready')).status_code == 200
    finally:
        app.dependency_overrides.clear()
