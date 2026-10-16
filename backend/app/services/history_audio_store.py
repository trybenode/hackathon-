"""Private S3 audio handoff between Vercel and external history workers; used by history_drafts."""
import asyncio
import os
from pathlib import Path
import re
from typing import Any
from uuid import uuid4

from app.core.config import get_settings
from app.services.feature_common import FeatureError

PREFIX = "history-audio/"
MAX_BYTES = 5 * 1024 * 1024


def _client() -> Any:
    """Use the existing server-side S3 credential configuration, never public URLs."""
    import boto3
    from botocore.config import Config
    cfg = get_settings()
    if not cfg.history_audio_bucket:
        raise FeatureError(503, "AUDIO_STORAGE_UNAVAILABLE", "Private audio storage is not configured.")
    return boto3.client("s3", endpoint_url=cfg.aws_endpoint_url_s3 or None,
                        region_name=cfg.aws_region or None,
                        aws_access_key_id=cfg.aws_access_key_id or None,
                        aws_secret_access_key=cfg.aws_secret_access_key or None,
                        config=Config(connect_timeout=3, read_timeout=10, retries={"total_max_attempts": 2}))


def _key(reference: str) -> str:
    """Only this configured bucket's random upload references may be read/deleted."""
    prefix = f"s3://{get_settings().history_audio_bucket}/"
    if not reference.startswith(prefix):
        raise FeatureError(503, "AUDIO_REFERENCE_INVALID", "Private recording is unavailable.")
    key = reference[len(prefix):]
    if not re.fullmatch(r"history-audio/[0-9a-f-]{36}\.upload", key):
        raise FeatureError(503, "AUDIO_REFERENCE_INVALID", "Private recording is unavailable.")
    return key


async def upload(data: bytes) -> str:
    """Persist bounded private bytes; a bucket lifecycle expires orphaned uploads."""
    if not data or len(data) > MAX_BYTES:
        raise FeatureError(422, "AUDIO_SIZE_INVALID", "Choose audio up to 5 MB.")
    key = f"{PREFIX}{uuid4()}.upload"
    def put() -> None:
        _client().put_object(Bucket=get_settings().history_audio_bucket, Key=key, Body=data,
                             ContentType="application/octet-stream", CacheControl="no-store",
                             ServerSideEncryption="AES256")
    try:
        await asyncio.to_thread(put)
    except FeatureError:
        raise
    except Exception:
        raise FeatureError(503, "AUDIO_STORAGE_UNAVAILABLE", "Private recording upload failed. Reconcile before retrying.") from None
    return f"s3://{get_settings().history_audio_bucket}/{key}"


async def download(reference: str, directory: Path) -> Path:
    """Materialize bounded bytes privately on the external worker for ffmpeg."""
    key = _key(reference)
    def get() -> Path:
        response = _client().get_object(Bucket=get_settings().history_audio_bucket, Key=key)
        body = response["Body"]
        try:
            if response.get("ContentLength", 0) > MAX_BYTES:
                raise ValueError("Audio size")
            data = body.read(MAX_BYTES + 1)
        finally:
            body.close()
        if not data or len(data) > MAX_BYTES:
            raise ValueError("Audio size")
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        if directory.is_symlink() or directory.stat().st_uid != os.getuid():
            raise ValueError("Private spool")
        directory.chmod(0o700)
        path = directory / f"{uuid4()}.upload"
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(data)
        except Exception:
            path.unlink(missing_ok=True)
            raise
        return path
    try:
        return await asyncio.to_thread(get)
    except Exception:
        raise FeatureError(503, "AUDIO_STORAGE_UNAVAILABLE", "Private recording could not be retrieved. Retry later.") from None


async def delete(reference: str) -> None:
    """Delete only an application-owned key; lifecycle remains a cleanup backstop."""
    key = _key(reference)
    try:
        await asyncio.to_thread(lambda: _client().delete_object(Bucket=get_settings().history_audio_bucket, Key=key))
    except Exception:
        raise FeatureError(503, "AUDIO_STORAGE_UNAVAILABLE", "Private recording cleanup is temporarily unavailable.") from None
