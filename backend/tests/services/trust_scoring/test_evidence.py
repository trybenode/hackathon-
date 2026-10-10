"""Missing evidence must not look like excellent or poor performance."""
from datetime import UTC, datetime
from types import SimpleNamespace
from app.services.trust_scoring.evidence import scoring_input
from app.services.trust_scoring.signals import aggregate


def row(**changes):
    data = dict(outcome_key="legacy", occurred_at=datetime.now(UTC), status=SimpleNamespace(value="completed"), cancelled_by=None, dispute_resolution=None, client_id=None, rating=None, quality_flags=[], source_platform="legacy", import_method="api", verified=True, available_signals=None)
    return SimpleNamespace(**(data | changes))


def test_defaults_do_not_claim_dispute_flags_client_or_rating_coverage():
    item = scoring_input(row())
    assert item["rating"] is None
    assert set(item["available_signals"]) == {"completion_rate", "cancellation_rate", "no_show_rate"}
    signals, _ = aggregate([item], {"completion_rate", "dispute_rate", "safety_incident_rate", "average_rating", "repeat_hire_rate"})
    assert signals == {"completion_rate": 1.0}


def test_explicit_absence_can_establish_coverage():
    item = scoring_input(row(), {"outcome": {"dispute_resolution": None, "quality_flags": []}})
    assert "dispute_rate" in item["available_signals"]
    assert "safety_incident_rate" in item["available_signals"]


def test_unknown_cancellation_and_disputed_status_do_not_invent_completion():
    for status in ("cancelled", "disputed", "unknown"):
        item = scoring_input(row(status=SimpleNamespace(value=status)))
        assert "completion_rate" not in item["available_signals"]


def test_missing_values_override_unusable_declared_rating_and_repeat_signals():
    item = scoring_input(row(available_signals=["average_rating", "repeat_hire_rate", "dispute_rate"]))
    assert "average_rating" not in item["available_signals"]
    assert "repeat_hire_rate" not in item["available_signals"]
    assert "dispute_rate" in item["available_signals"]


def test_client_identifiers_are_namespaced_to_source():
    first = scoring_input(row(client_id="1", source_platform="A"))
    second = scoring_input(row(client_id="1", source_platform="B"))
    signals, _ = aggregate([first, second], {"repeat_hire_rate"})
    assert signals["repeat_hire_rate"] == 0


def test_legacy_credential_defaults_do_not_add_absence_evidence():
    item = scoring_input(row(normalization_version="credential-v1"), {"dispute_resolution": None, "flags": []})
    assert "dispute_rate" not in item["available_signals"]
    assert "safety_incident_rate" not in item["available_signals"]


def test_legacy_disputed_payload_does_not_prove_completion():
    item = scoring_input(row(), {"outcome": {"status": "disputed"}})
    assert "completion_rate" not in item["available_signals"]


def test_explicit_signal_coverage_is_preserved():
    item = scoring_input(row(available_signals=[]))
    assert item["available_signals"] == []
