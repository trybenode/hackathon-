"""Average ratings treat missing values as zero rather than skipping jobs."""

from app.services.trust_scoring.signals import aggregate


def test_average_rating_excludes_missing_ratings() -> None:
    jobs = [
        {"status": "completed", "rating": 4.0},
        {"status": "completed"},
    ]

    signals, count = aggregate(jobs, {"average_rating"})

    assert count == 2
    assert signals["average_rating"] == 0.8


def test_average_rating_excludes_null_ratings() -> None:
    jobs = [
        {"status": "completed", "rating": 5.0},
        {"status": "completed", "rating": None},
    ]

    signals, _ = aggregate(jobs, {"average_rating"})

    assert signals["average_rating"] == 1.0


def test_absent_evidence_is_not_a_perfect_signal():
    jobs = [{"status": "completed", "available_signals": ["completion_rate"]} for _ in range(10)]
    signals, count = aggregate(jobs, {"completion_rate", "dispute_rate", "safety_incident_rate", "average_rating"})
    assert count == 10
    assert signals == {"completion_rate": 1.0}
