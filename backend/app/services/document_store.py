"""Purpose: Put KYC documents in object storage and keep only the reference.

Dependencies: boto3 against the S3-compatible bucket in the environment.
Used by: the guarantor identity submission.

The document itself never reaches the database; the bucket holds the bytes and
the row holds the key, per AGENT.md. Uploads are private, and the key is
unguessable so a leaked reference alone is not a directory listing.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Protocol

from app.core.config import get_settings

logger = logging.getLogger(__name__)

#: Extensions the identity screen accepts.
ALLOWED_SUFFIXES = {".pdf", ".jpg", ".jpeg", ".png"}
#: Refuse anything larger, before it reaches the bucket.
MAX_DOCUMENT_BYTES = 10 * 1024 * 1024


class DocumentTooLargeError(Exception):
    """The upload exceeds the size the bucket will accept."""


class UnsupportedDocumentError(Exception):
    """The upload is not a format we accept."""


@dataclass(frozen=True)
class StoredDocument:
    """Where a document went. Never the document itself."""

    reference: str
    size: int


class DocumentStore(Protocol):
    name: str

    async def store(self, *, filename: str, content: bytes, prefix: str) -> StoredDocument: ...


def _validate(filename: str, content: bytes) -> str:
    suffix = PurePosixPath(filename or "").suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise UnsupportedDocumentError(
            f"Only {', '.join(sorted(ALLOWED_SUFFIXES))} files are accepted."
        )
    if len(content) > MAX_DOCUMENT_BYTES:
        raise DocumentTooLargeError(
            f"Documents must be under {MAX_DOCUMENT_BYTES // (1024 * 1024)}MB."
        )
    return suffix


class NullDocumentStore:
    """Drops the document and reports it.

    Used when no bucket is configured, so local work without S3 credentials
    still exercises the flow.
    """

    name = "null"

    async def store(self, *, filename: str, content: bytes, prefix: str) -> StoredDocument:
        _validate(filename, content)
        logger.info("No bucket configured; discarded %s (%d bytes)", filename, len(content))
        return StoredDocument(reference="", size=len(content))


class S3DocumentStore:
    """Stores documents in the configured S3-compatible bucket."""

    name = "s3"

    def __init__(
        self,
        *,
        bucket: str,
        endpoint_url: str | None,
        region: str | None,
        access_key_id: str | None = None,
        secret_access_key: str | None = None,
    ) -> None:
        self.bucket = bucket
        self.endpoint_url = endpoint_url or None
        self.region = region or None
        self.access_key_id = access_key_id or None
        self.secret_access_key = secret_access_key or None

    def _client(self):
        import boto3

        # Credentials come from settings because boto3's own discovery reads
        # the process environment, which never sees .env.
        return boto3.client(
            "s3",
            endpoint_url=self.endpoint_url,
            region_name=self.region,
            aws_access_key_id=self.access_key_id,
            aws_secret_access_key=self.secret_access_key,
        )

    async def store(self, *, filename: str, content: bytes, prefix: str) -> StoredDocument:
        suffix = _validate(filename, content)
        # A random name: the original filename may carry personal information,
        # and predictable keys invite guessing.
        key = f"{prefix}/{uuid.uuid4().hex}{suffix}"

        def upload() -> None:
            self._client().put_object(
                Bucket=self.bucket,
                Key=key,
                Body=content,
                ContentType={
                    ".pdf": "application/pdf",
                    ".png": "image/png",
                    ".jpg": "image/jpeg",
                    ".jpeg": "image/jpeg",
                }[suffix],
            )

        # boto3 is synchronous; keep it off the event loop.
        await asyncio.to_thread(upload)
        logger.info("Stored document at %s", key)
        return StoredDocument(reference=key, size=len(content))


def build_default_store() -> DocumentStore:
    settings = get_settings()
    if settings.s3_bucket.strip():
        return S3DocumentStore(
            bucket=settings.s3_bucket,
            endpoint_url=settings.aws_endpoint_url_s3,
            region=settings.aws_region,
            access_key_id=settings.aws_access_key_id,
            secret_access_key=settings.aws_secret_access_key,
        )

    return NullDocumentStore()


default_document_store: DocumentStore = build_default_store()
