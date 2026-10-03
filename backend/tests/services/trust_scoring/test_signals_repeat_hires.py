"""Repeat-hire signals require known client identities."""

from app.services.trust_scoring.signals import aggregate


def test_repeat_hire_signal_is_omitted_when_client_ids_are_unknown() -> None:
    jobs = [
        {"status": "completed", "client_id": None},
        {"status": "completed", "client_id": None},
    ]

    signals, count = aggregate(jobs, {"repeat_hire_rate"})

    assert count == 2
    assert "repeat_hire_rate" not in signals


def test_repeat_hire_rate_ignores_rows_without_client_identity() -> None:
    jobs = [
        {"status": "completed", "client_id": "client-a"},
        {"status": "completed", "client_id": "client-a"},
        {"status": "completed", "client_id": None},
    ]

    signals, _ = aggregate(jobs, {"repeat_hire_rate"})

    assert signals["repeat_hire_rate"] == 1.0
