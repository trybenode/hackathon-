"""
Property-based tests for score_worker.

These test one property that must hold no matter what: score_worker should
never raise an exception, for any combination of tracked signals, job
counts, or preset. This is what caught a real divide-by-zero bug (empty
`used`) automatically during development.
"""
from hypothesis import given, strategies as st, settings, HealthCheck
from app.services.trust_scoring.scoring import score_worker, PRESETS, NORMALIZERS

ALL_SIGNAL_NAMES = list(NORMALIZERS.keys())

signals_strategy = st.dictionaries(
    keys=st.sampled_from(ALL_SIGNAL_NAMES),
    values=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
    max_size=len(ALL_SIGNAL_NAMES),
)

n_jobs_strategy = st.integers(min_value=0, max_value=1000)
preset_strategy = st.sampled_from(list(PRESETS.values()))


@given(signals=signals_strategy, n_jobs=n_jobs_strategy, cfg=preset_strategy)
@settings(suppress_health_check=[HealthCheck.too_slow], max_examples=300)
def test_score_worker_never_crashes(signals, n_jobs, cfg):
    result = score_worker(signals, n_jobs, cfg)
    assert isinstance(result, dict)


@given(signals=signals_strategy, n_jobs=n_jobs_strategy, cfg=preset_strategy)
@settings(suppress_health_check=[HealthCheck.too_slow], max_examples=300)
def test_score_worker_always_returns_contract_keys(signals, n_jobs, cfg):
    result = score_worker(signals, n_jobs, cfg)
    expected_keys = {"decision", "confidence", "score", "band", "status",
                      "signals_used", "explanation_summary"}
    assert expected_keys.issubset(result.keys())


@given(signals=signals_strategy, n_jobs=n_jobs_strategy, cfg=preset_strategy)
@settings(suppress_health_check=[HealthCheck.too_slow], max_examples=300)
def test_confidence_always_in_valid_range(signals, n_jobs, cfg):
    result = score_worker(signals, n_jobs, cfg)
    assert 0.0 <= result["confidence"] <= 1.0


@given(signals=signals_strategy, n_jobs=n_jobs_strategy, cfg=preset_strategy)
@settings(suppress_health_check=[HealthCheck.too_slow], max_examples=300)
def test_score_is_in_range_and_matches_the_band(signals, n_jobs, cfg):
    """The band is cut from the score, so the two can never disagree."""
    result = score_worker(signals, n_jobs, cfg)
    if result["status"] != "Scored":
        assert result["score"] is None
        return

    score = result["score"]
    assert 0.0 <= score <= 1.0
    # The thresholds apply to the unrounded score; allow for the rounding.
    if result["band"] == "High":
        assert score >= cfg.high_t - 1e-4
    elif result["band"] == "Medium":
        assert cfg.medium_t - 1e-4 <= score < cfg.high_t + 1e-4
    else:
        assert score < cfg.medium_t + 1e-4


@given(signals=signals_strategy, cfg=preset_strategy)
@settings(suppress_health_check=[HealthCheck.too_slow], max_examples=200)
def test_zero_jobs_never_crashes(signals, cfg):
    """
    Zero jobs does NOT always mean "Building History": if a hard_fail signal
    is present, decision #3 (hard-fails apply immediately, before min_jobs)
    would disqualify even at n_jobs=0. No preset currently configures a
    hard_fail, so this test asserts that invariant holds and that zero jobs
    means Building History — if a preset ever gets a hard_fail again, this
    test should be revisited alongside that decision.
    """
    assert cfg.hard_fail == {}, (
        "A preset has a hard_fail configured again — re-check whether "
        "permanent disqualification is intended before assuming this "
        "test's zero-jobs assertion still holds."
    )
    result = score_worker(signals, 0, cfg)
    assert result["band"] == "Building History"
