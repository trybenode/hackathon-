"""Private evidence attachments for ownership review; used only by import/reviewer services."""

import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any
import os
from pathlib import Path
import re
import tempfile
from uuid import uuid4
from app.core.config import get_settings
from app.services.feature_common import FeatureError

MAX_DOCUMENT = 3 * 1024 * 1024


def document_type(data: bytes) -> str:
    """Validate permitted file signatures; no inline rendering or authenticity claim."""
    if not data or len(data) > MAX_DOCUMENT:
        raise FeatureError(
            422, "DOCUMENT_SIZE", "Supporting documents must be at most 3 MiB."
        )
    if data.startswith(b"%PDF-") and b"%%EOF" in data[-4096:]:
        return "application/pdf"
    if data.startswith(b"\xff\xd8\xff") and data.endswith(b"\xff\xd9"):
        return "image/jpeg"
    if (
        data.startswith(b"\x89PNG\r\n\x1a\n")
        and len(data) >= 24
        and data[12:16] == b"IHDR"
    ):
        width, height = int.from_bytes(data[16:20], "big"), int.from_bytes(
            data[20:24], "big"
        )
        if 0 < width <= 20000 and 0 < height <= 20000:
            return "image/png"
    raise FeatureError(
        422, "DOCUMENT_TYPE", "Use a PDF, JPEG or PNG supporting document."
    )


def root() -> Path:
    """Development-only local storage, separate from public assets and user filenames."""
    return Path(
        get_settings().ownership_storage_dir
        or f"{tempfile.gettempdir()}/trust-ownership-{os.getuid()}"
    )


def client() -> Any:
    """Construct the existing private S3 client with bounded network timeouts."""
    import boto3
    from botocore.config import Config

    cfg = get_settings()
    if not cfg.s3_bucket or (
        cfg.aws_endpoint_url_s3 and not cfg.aws_endpoint_url_s3.startswith("https://")
    ):
        raise FeatureError(
            503, "EVIDENCE_STORAGE", "Private evidence storage is not configured."
        )
    return boto3.client(
        "s3",
        region_name=cfg.aws_region or None,
        endpoint_url=cfg.aws_endpoint_url_s3 or None,
        aws_access_key_id=cfg.aws_access_key_id or None,
        aws_secret_access_key=cfg.aws_secret_access_key or None,
        config=Config(
            connect_timeout=3, read_timeout=10, retries={"total_max_attempts": 2}
        ),
    )


def validate_key(key: str) -> None:
    """Do not allow path traversal or references to identity documents/other prefixes."""
    if not re.fullmatch(r"ownership-review/[0-9a-f]{32}", key):
        raise FeatureError(
            404, "DOCUMENT_NOT_FOUND", "Supporting document unavailable."
        )


async def store(data: bytes, content_type: str) -> str:
    """Store encrypted private evidence; no null provider may report success."""
    key = f"ownership-review/{uuid4().hex}"

    def write() -> None:
        cfg = get_settings()
        if cfg.s3_bucket:
            client().put_object(
                Bucket=cfg.s3_bucket,
                Key=key,
                Body=data,
                ContentType=content_type,
                CacheControl="no-store",
                ServerSideEncryption="AES256",
            )
        elif cfg.environment == "development":
            directory = root()
            directory.mkdir(parents=True, exist_ok=True, mode=0o700)
            if directory.is_symlink() or directory.stat().st_uid != os.getuid():
                raise ValueError("Unsafe local storage")
            directory.chmod(0o700)
            fd = os.open(
                directory / key.split("/")[1],
                os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                0o600,
            )
            with os.fdopen(fd, "wb") as stream:
                stream.write(data)
        else:
            raise ValueError("Private S3 required")

    try:
        await asyncio.to_thread(write)
    except Exception:
        raise FeatureError(
            503,
            "EVIDENCE_STORAGE",
            "Supporting document could not be stored privately.",
        ) from None
    return key


async def read(key: str) -> bytes:
    """Retrieve bounded evidence only after the caller authorizes the reviewer."""
    validate_key(key)

    def fetch() -> bytes:
        cfg = get_settings()
        if cfg.s3_bucket:
            response = client().get_object(Bucket=cfg.s3_bucket, Key=key)
            stream = response["Body"]
            try:
                return stream.read(MAX_DOCUMENT + 1)
            finally:
                stream.close()
        if cfg.environment != "development":
            raise ValueError("No private storage")
        return (root() / key.split("/")[1]).read_bytes()

    try:
        data = await asyncio.to_thread(fetch)
        if len(data) > MAX_DOCUMENT:
            raise ValueError("Size")
        return data
    except Exception:
        raise FeatureError(
            503, "EVIDENCE_STORAGE", "Supporting document is temporarily unavailable."
        ) from None


async def delete(key: str) -> None:
    """Remove an expired evidence object; retention jobs retry failed deletions."""
    validate_key(key)

    def remove() -> None:
        cfg = get_settings()
        if cfg.s3_bucket:
            client().delete_object(Bucket=cfg.s3_bucket, Key=key)
        elif cfg.environment == "development":
            (root() / key.split("/")[1]).unlink(missing_ok=True)
        else:
            raise ValueError("No private storage")

    try:
        await asyncio.to_thread(remove)
    except Exception:
        raise FeatureError(
            503, "EVIDENCE_STORAGE", "Evidence deletion will be retried."
        ) from None


async def object_pages() -> AsyncIterator[list[tuple[str, datetime]]]:
    """List only the evidence prefix for scheduled orphan cleanup, one bounded page at a time."""
    cfg = get_settings()
    if cfg.s3_bucket:
        storage = client()
        token: str | None = None
        while True:
            kwargs: dict[str, Any] = {
                "Bucket": cfg.s3_bucket,
                "Prefix": "ownership-review/",
                "MaxKeys": 1000,
            }
            if token:
                kwargs["ContinuationToken"] = token
            result = await asyncio.to_thread(storage.list_objects_v2, **kwargs)
            yield [
                (obj["Key"], obj["LastModified"]) for obj in result.get("Contents", [])
            ]
            token = result.get("NextContinuationToken")
            if not token:
                break
    elif cfg.environment == "development" and root().exists():
        # Local development uses this only for test/pilot attachments.
        files = await asyncio.to_thread(
            lambda: [
                (
                    f"ownership-review/{p.name}",
                    datetime.fromtimestamp(p.stat().st_mtime, UTC),
                )
                for p in root().iterdir()
                if p.is_file()
            ]
        )
        for offset in range(0, len(files), 1000):
            yield files[offset : offset + 1000]
