"""Tests for converting persisted outcome rows to scorer input."""

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace

from app.services.normalisation import normalise_db_row
from app.services.trust_scoring.evidence import scoring_input


def test_scoring_adapter_maps_fields_without_inventing_rating() -> None:
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

    result = scoring_input(row)

    assert result == {
        "available_signals": ["cancellation_rate", "completion_rate", "damage_report_rate", "dispute_rate", "no_show_rate", "repeat_hire_rate"],
        "job_id": "source-job-17",
        "date": occurred_at,
        "status": "completed",
        "cancelled_by": None,
        "dispute_resolution": "dismissed",
        "client_id": "native:client-1",
        "rating": None,
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
