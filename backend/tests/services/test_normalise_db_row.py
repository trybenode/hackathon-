"""Tests for converting persisted outcome rows to scorer input."""

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace

from app.services.normalisation import normalise_db_row


def test_normalise_db_row_maps_scoring_fields_and_defaults_rating() -> None:
    occurred_at = datetime(2026, 10, 4, tzinfo=UTC)
    row = SimpleNamespace(
        outcome_key="source-job-17",
        occurred_at=occurred_at,
        status=SimpleNamespace(value="completed"),
        cancelled_by=None,
        dispute_resolution="dismissed",
        client_id="client-1",
        rating=None,
        quality_flags=["damage", "on_time"],
        source_platform="native",
        import_method="api",
        verified=True,
    )

    result = normalise_db_row(row)

    assert result == {
        "job_id": "source-job-17",
        "date": occurred_at,
        "status": "completed",
        "cancelled_by": None,
        "dispute_resolution": "dismissed",
        "client_id": "client-1",
        "rating": 0.0,
        "flags": ["damage"],
        "source_platform": "native",
        "import_method": "api",
        "verified": True,
    }


def test_normalise_db_row_converts_decimal_rating() -> None:
    row = SimpleNamespace(
        outcome_key="job-2",
        occurred_at=datetime(2026, 10, 4, tzinfo=UTC),
        status=SimpleNamespace(value="completed"),
        cancelled_by=None,
        dispute_resolution=None,
        client_id=None,
        rating=Decimal("4.5"),
        quality_flags=[],
        source_platform="native",
        import_method="native",
        verified=True,
    )

    assert normalise_db_row(row)["rating"] == 4.5
