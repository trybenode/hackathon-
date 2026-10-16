"""Private cross-host audio handoff, bounded reads and retry behavior; no cloud bucket calls."""
import io
from pathlib import Path
import pytest
from app.core.config import get_settings
from app.services import history_audio_store as store, history_drafts
from app.services.feature_common import FeatureError


@pytest.fixture
def fake_bucket(monkeypatch):
    cfg = get_settings()
    monkeypatch.setattr(cfg, "history_audio_bucket", "audio-test")
    objects = {}
    class S3:
        def put_object(self, **kwargs):
            assert kwargs["ServerSideEncryption"] == "AES256"
            objects[kwargs["Key"]] = kwargs["Body"]
        def get_object(self, **kwargs):
            data = objects[kwargs["Key"]]
            return {"Body": io.BytesIO(data), "ContentLength": len(data)}
        def delete_object(self, **kwargs):
            objects.pop(kwargs["Key"], None)
    monkeypatch.setattr(store, "_client", S3)
    return objects


async def test_private_roundtrip_and_reference_isolation(fake_bucket, tmp_path):
    reference = await store.upload(b"private recording")
    assert reference.startswith("s3://audio-test/history-audio/")
    local = await store.download(reference, tmp_path)
    assert local.read_bytes() == b"private recording"
    assert local.stat().st_mode & 0o777 == 0o600
    with pytest.raises(FeatureError):
        await store.delete(reference.replace("audio-test", "another-tenant"))
    with pytest.raises(FeatureError):
        await store.download("s3://audio-test/history-audio/../../secret", tmp_path)
    await store.delete(reference)
    assert not fake_bucket


async def test_storage_failure_and_size_bounds(fake_bucket, monkeypatch):
    with pytest.raises(FeatureError):
        await store.upload(b"x" * (store.MAX_BYTES + 1))
    def fail():
        raise RuntimeError("secret provider credentials")
    monkeypatch.setattr(store, "_client", fail)
    with pytest.raises(FeatureError) as error:
        await store.upload(b"private")
    assert error.value.code == "AUDIO_STORAGE_UNAVAILABLE"
    assert "secret" not in str(error.value)


@pytest.fixture
def external_config(monkeypatch, tmp_path):
    cfg = get_settings()
    monkeypatch.setattr(cfg, "environment", "development")
    monkeypatch.setattr(cfg, "history_ai_enabled", True)
    monkeypatch.setattr(cfg, "history_ai_base_url", "http://model.test")
    monkeypatch.setattr(cfg, "history_audio_dir", str(tmp_path))
    return tmp_path


async def test_s3_voice_processing_uses_external_worker(session, worker, external_config, fake_bucket, monkeypatch):
    from sqlalchemy.ext.asyncio import async_sessionmaker
    from app.models.domain import User
    from app.models.history import HistoryDraft
    from app.schemas.history import ClaimDetails
    from app.services.history_ai import HistoryModelGateway
    from uuid import uuid4
    cfg = get_settings(); monkeypatch.setattr(cfg, "history_audio_storage", "s3")
    user = await session.get(User, worker.user_id)
    draft = await history_drafts.enqueue(session, user, b"recording", "en", None, uuid4())
    await session.commit()
    async def normalize(path):
        assert path.read_bytes() == b"recording"
        return path
    async def transcribe(self, path, language):
        return "Fixed a tap", {"asr": "fixture", "revision": "fixture"}
    async def extract(self, transcript, language):
        return ClaimDetails(work_type="Plumbing", description=transcript, claimed_completed=False)
    monkeypatch.setattr(history_drafts, "normalize_audio", normalize)
    monkeypatch.setattr(HistoryModelGateway, "transcribe", transcribe)
    monkeypatch.setattr(HistoryModelGateway, "extract", extract)
    assert await history_drafts.process_one(async_sessionmaker(session.bind, expire_on_commit=False))
    session.expire_all()
    row = await session.get(HistoryDraft, draft.id)
    assert row.status == "ready" and row.claim_id is None and row.audio_path is None
    assert not fake_bucket
    assert not list(external_config.glob("*.upload"))


async def test_serverless_upload_cap_applies_before_storage(session, worker, external_config, fake_bucket, monkeypatch):
    from app.models.domain import User
    from uuid import uuid4
    monkeypatch.setattr(get_settings(), "deployment_mode", "serverless")
    user = await session.get(User, worker.user_id)
    with pytest.raises(FeatureError) as error:
        await history_drafts.enqueue(session, user, b"x" * (3 * 1024 * 1024 + 1), "en", None, uuid4())
    assert error.value.code == "AUDIO_SIZE_INVALID"
    assert not fake_bucket
