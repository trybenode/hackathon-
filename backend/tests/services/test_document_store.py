"""Purpose: Verify the S3 document store fails cleanly when the bucket is unreachable.

Dependencies: pytest, botocore, and app.services.document_store.
Used by: the backend test suite and CI.
"""

import pytest
from botocore.exceptions import EndpointConnectionError

from app.services.document_store import DocumentStorageError, S3DocumentStore


class _UnreachableClient:
    def put_object(self, **_: object) -> None:
        raise EndpointConnectionError(endpoint_url="https://storage.example.test")


async def test_connection_failure_becomes_a_storage_error(monkeypatch: pytest.MonkeyPatch) -> None:
    store = S3DocumentStore(bucket="ids", endpoint_url="https://storage.example.test", region="eu")
    monkeypatch.setattr(store, "_client", lambda: _UnreachableClient())

    with pytest.raises(DocumentStorageError):
        await store.store(filename="bill.pdf", content=b"%PDF-1.4", prefix="guarantor-documents/x")
