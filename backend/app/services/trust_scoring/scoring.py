from dataclasses import dataclass, field

@dataclass(frozen=True)
class PlatformConfig:
    weights: dict = field(default_factory=lambda: {
        "completion_rate": 0.35, "dispute_rate": 0.25, "no_show_rate": 0.15,
        "repeat_hire_rate": 0.15, "cancellation_rate": 0.10})
    required_signals: tuple = ("completion_rate", "dispute_rate")
    hard_fail: dict = field(default_factory=dict)   # signal -> max allowed raw value
    min_jobs: int = 5
    high_t: float = 0.80
    medium_t: float = 0.60
    baseline: float = 0.60
    k: int = 10                                     # evidence term = 0.5 at n = k
    building_history_decision: bool = False

PRESETS = {
    "generic": PlatformConfig(),
    "domestic": PlatformConfig(
        weights={"safety_incident_rate": 0.30, "completion_rate": 0.25,
                 "dispute_rate": 0.20, "repeat_hire_rate": 0.15, "no_show_rate": 0.10},
        required_signals=("completion_rate", "safety_incident_rate"),
        min_jobs=8, baseline=0.70),
    "ride_hailing": PlatformConfig(
        weights={"completion_rate": 0.35, "cancellation_rate": 0.30,
                 "dispute_rate": 0.35},
        required_signals=("completion_rate", "dispute_rate"), min_jobs=10),
}

NORMALIZERS = {  # all map to [0,1], higher = better
    "completion_rate":      lambda x: x,
    "dispute_rate":         lambda x: max(0.0, 1 - x / 0.10),
    "cancellation_rate":    lambda x: max(0.0, 1 - x / 0.20),
    "no_show_rate":         lambda x: max(0.0, 1 - x / 0.10),
    "safety_incident_rate": lambda x: max(0.0, 1 - x / 0.02),
    "rework_rate":          lambda x: max(0.0, 1 - x / 0.15),
    "damage_report_rate":   lambda x: max(0.0, 1 - x / 0.05),
    "repeat_hire_rate":     lambda x: min(1.0, x / 0.30),  # placeholder, tune on seed data
}

def score_worker(signals: dict, n_jobs: int, cfg: PlatformConfig) -> dict:
    used = [s for s in cfg.weights if s in signals]
    missing = [s for s in cfg.required_signals if s not in signals]
    evidence = n_jobs / (n_jobs + cfg.k)

    # Hard-fail check runs first and unconditionally, even under min_jobs.
    # No preset currently has a hard_fail configured (permanent safety
    # disqualification was deliberately removed as too harsh), but the
    # mechanism stays in place in case one is reintroduced later.
    failed = [s for s, mx in cfg.hard_fail.items() if signals.get(s, 0) > mx]
    if failed:
        return {"decision": False, "confidence": round(evidence, 2),
                "band": "Low", "status": "Disqualified", "signals_used": used,
                "explanation_summary": f"Failed hard rule: {failed[0]}"}

    # Guard: not enough history, missing required signals, OR no overlap at
    # all between what this platform tracks and what this preset weighs.
    # Without this, total_w below would be 0 and the division would crash.
    if n_jobs < cfg.min_jobs or missing or not used:
        return {"decision": cfg.building_history_decision,
                "confidence": round(evidence, 2),
                "band": "Building History", "status": "Building History",
                "signals_used": used,
                "explanation_summary": "Not enough verified job history yet"
                if used else "Platform's tracked signals do not overlap this preset"}

    norm = {s: NORMALIZERS[s](signals[s]) for s in used}
    total_w = sum(cfg.weights[s] for s in used)
    score = sum(cfg.weights[s] * norm[s] for s in used) / total_w
    coverage = total_w / sum(cfg.weights.values())
    confidence = round(evidence * coverage, 2)

    band = ("High" if score >= cfg.high_t else
            "Medium" if score >= cfg.medium_t else "Low")
    decision = score >= cfg.baseline
    weakest = min(norm, key=norm.get)
    summary = f"Score {score:.2f} vs baseline {cfg.baseline:.2f}; weakest signal: {weakest}"

    return {"decision": decision, "confidence": confidence, "band": band,
            "status": "Scored", "signals_used": used, "explanation_summary": summary}


def starting_rating(signals: dict, n_jobs: int) -> dict:
    """
    Separate, capped, unverified rating for imported-only workers who never
    have enough data to go through score_worker. Uses only completion_rate
    and cancellation_rate, since imports only ever supply job_id, date,
    status. Capped at 0.65 so it can never read as the top tier. Does not
    call score_worker and shares no state with it.
    """
    completion = signals.get("completion_rate", 0)
    cancellation = signals.get("cancellation_rate", 0)
    raw = (0.6 * NORMALIZERS["completion_rate"](completion)
           + 0.4 * NORMALIZERS["cancellation_rate"](cancellation))
    capped = min(raw, 0.65)
    return {"starting_rating": round(capped, 2), "verified": False,
            "label": "Building History (imported)"}
