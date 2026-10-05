"""Average ratings treat missing values as zero rather than skipping jobs."""

from app.services.trust_scoring.signals import aggregate


def test_average_rating_counts_missing_rating_as_zero() -> None:
    jobs = [
        {"status": "completed", "rating": 4.0},
        {"status": "completed"},
    ]

    signals, count = aggregate(jobs, {"average_rating"})

    assert count == 2
    assert signals["average_rating"] == 0.4


def test_average_rating_counts_null_rating_as_zero() -> None:
    jobs = [
        {"status": "completed", "rating": 5.0},
        {"status": "completed", "rating": None},
    ]

    signals, _ = aggregate(jobs, {"average_rating"})

    assert signals["average_rating"] == 0.5
