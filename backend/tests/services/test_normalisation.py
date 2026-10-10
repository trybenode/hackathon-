"""
Tests for app.services.normalisation.

Hand-picked cases cover the specific decisions baked into this module (the
disputed-status default, flag filtering, unmappable-status skipping). A
property test guards normalise_import against crashing on arbitrary rows.
"""
import pytest
from hypothesis import given, strategies as st, settings, HealthCheck
from app.services.normalisation import (
    normalise_native,
    normalise_outcome_event,
    normalise_import,
    merge_imported_sources,
    STATUS_MAPS,
)


# ---------------------------------------------------------------------------
# normalise_native
# ---------------------------------------------------------------------------

def test_native_missing_required_field_raises():
    with pytest.raises(ValueError):
        normalise_native({"job_id": "j1", "status": "completed"})  # no date


def test_native_filters_unknown_flags():
    job = {"job_id": "j1", "date": "2026-09-20", "status": "completed",
           "flags": ["safety", "on_time", "rework"]}
    result = normalise_native(job)
    assert result["flags"] == ["safety", "rework"]  # on_time dropped


def test_native_stamps_provenance():
    job = {"job_id": "j1", "date": "2026-09-20", "status": "completed"}
    result = normalise_native(job)
    assert result["source_platform"] == "native"
    assert result["import_method"] == "native"
    assert result["verified"] is True


# ---------------------------------------------------------------------------
# normalise_outcome_event — the disputed-status mapping is the core thing
# to protect here, since it's a documented assumption, not a certainty.
# ---------------------------------------------------------------------------

def _outcome_payload(status, **overrides):
    outcome = {"status": status, "rating": 4.0, "completion_confirmed": True,
               "quality_flags": [], "dispute_reason": None,
               "evidence_urls": [], "completed_at": "2026-09-19T18:30:00Z"}
    outcome.update(overrides)
    return {"worker_id": "w1", "job_id": "j1", "platform_id": "p1",
            "platform_type": "domestic", "outcome": outcome, "raw_payload": {}}


def test_disputed_status_maps_to_completed_with_open_dispute():
    payload = _outcome_payload("disputed")
    result = normalise_outcome_event(payload)
    assert result["status"] == "completed"
    assert result["dispute_resolution"] == "open"


def test_normal_status_passes_through_with_no_dispute():
    payload = _outcome_payload("completed")
    result = normalise_outcome_event(payload)
    assert result["status"] == "completed"
    assert result["dispute_resolution"] is None


def test_outcome_event_never_guesses_client_id():
    payload = _outcome_payload("completed")
    result = normalise_outcome_event(payload)
    assert result["client_id"] is None


def test_outcome_event_unrecognised_status_raises():
    payload = _outcome_payload("some_made_up_status")
    with pytest.raises(ValueError):
        normalise_outcome_event(payload)


def test_outcome_event_filters_quality_flags():
    payload = _outcome_payload("completed", quality_flags=["on_time", "damage"])
    result = normalise_outcome_event(payload)
    assert result["flags"] == ["damage"]


# ---------------------------------------------------------------------------
# normalise_import
# ---------------------------------------------------------------------------

def test_import_unmappable_status_is_skipped_not_guessed():
    rows = [
        {"job_id": "t1", "date": "2026-09-01", "status": "COMPLETED"},
        {"job_id": "t2", "date": "2026-09-02", "status": "TOTALLY_UNKNOWN"},
    ]
    result = normalise_import(rows, "ridehailing_generic")
    assert len(result) == 1
    assert result[0]["job_id"] == "t1"


def test_handyman_import_maps_statuses_and_skips_rework():
    rows = [
        {"job_id": "h1", "date": "2026-09-01", "status": "JOB_COMPLETED"},
        {"job_id": "h2", "date": "2026-09-02", "status": "PRO_CANCELLED"},
        {"job_id": "h3", "date": "2026-09-03", "status": "CLIENT_CANCELLED"},
        {"job_id": "h4", "date": "2026-09-04", "status": "NO_SHOW"},
        {"job_id": "h5", "date": "2026-09-05", "status": "REWORK_REQUESTED"},
    ]
    result = normalise_import(rows, "handyman_generic")
    assert len(result) == 4
    assert all(r["job_id"] != "h5" for r in result)
    assert [r["status"] for r in result] == ["completed", "cancelled", "cancelled", "no_show"]


def test_import_never_includes_native_only_fields():
    rows = [{"job_id": "t1", "date": "2026-09-01", "status": "COMPLETED"}]
    result = normalise_import(rows, "ridehailing_generic")[0]
    for field in ("cancelled_by", "dispute_resolution", "client_id", "rating", "flags"):
        assert field not in result


def test_import_unverified_and_csv_upload():
    rows = [{"job_id": "t1", "date": "2026-09-01", "status": "COMPLETED"}]
    result = normalise_import(rows, "ridehailing_generic")[0]
    assert result["verified"] is False
    assert result["import_method"] == "csv_upload"


def test_import_unknown_source_raises():
    with pytest.raises(ValueError):
        normalise_import([], "some_platform_with_no_mapping")


# ---------------------------------------------------------------------------
# merge_imported_sources
# ---------------------------------------------------------------------------

def test_merge_combines_all_sources_into_one_list():
    a = [{"job_id": "a1"}]
    b = [{"job_id": "b1"}, {"job_id": "b2"}]
    merged = merge_imported_sources(a, b)
    assert len(merged) == 3


def test_merge_with_no_sources_returns_empty_list():
    assert merge_imported_sources() == []


# ---------------------------------------------------------------------------
# Property test: normalise_import should never crash on arbitrary row data,
# for a known source, regardless of what garbage a status field contains.
# ---------------------------------------------------------------------------

row_strategy = st.fixed_dictionaries({
    "job_id": st.text(min_size=1, max_size=20),
    "date": st.text(min_size=1, max_size=20),
    "status": st.one_of(st.text(max_size=20), st.none()),
})

rows_strategy = st.lists(row_strategy, max_size=20)


@given(rows=rows_strategy)
@settings(suppress_health_check=[HealthCheck.too_slow], max_examples=200)
def test_normalise_import_never_crashes_on_arbitrary_rows(rows):
    result = normalise_import(rows, "ridehailing_generic")
    assert isinstance(result, list)
    # every returned row must have a status that was actually in our map's
    # value set — never an unmapped/invented status
    valid_statuses = set(STATUS_MAPS["ridehailing_generic"].values())
    for row in result:
        assert row["status"] in valid_statuses
