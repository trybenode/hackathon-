from collections import Counter

CORE = {"completion_rate", "cancellation_rate", "dispute_rate"}

# signal -> predicate over an eligible job; flags carry vertical-specific events.
# No "late" predicate — that signal was removed from the design (see
# docs/signal_definitions.md and docs/flag_integrity.md): without a scheduled
# time captured at booking, there's no reliable way to know who was late.
SIGNAL_DEFS = {
    "completion_rate":      lambda j: j["status"] == "completed",
    "cancellation_rate":    lambda j: j["status"] == "cancelled",
    "no_show_rate":         lambda j: j["status"] == "no_show",
    "dispute_rate":         lambda j: j.get("dispute_resolution") in ("open", "upheld"),
    "safety_incident_rate": lambda j: "safety" in j.get("flags", ()),
    "rework_rate":          lambda j: "rework" in j.get("flags", ()),
    "damage_report_rate":   lambda j: "damage" in j.get("flags", ()),
}


def aggregate(jobs: list[dict], tracked: set[str]) -> tuple[dict, int]:
    """
    Turn a worker's raw job records into signal rates.

    Client- and platform-caused cancellations are excluded before counting,
    since they were never the worker's to complete (see docs/schema_spec.md).
    Only signals in `tracked` are computed, so a platform that doesn't report
    a given signal never has it silently default to a value that could be
    misread as "perfect" (the original bug this fixed: an unreported
    safety_incident_rate defaulting to 0, which the normalizer scores as 1.0).
    """
    jobs = [j for j in jobs
            if not (j["status"] == "cancelled" and j.get("cancelled_by") in ("client", "platform"))]
    n = len(jobs)
    if n == 0:
        return {}, 0

    signals = {s: sum(map(pred, jobs)) / n
               for s, pred in SIGNAL_DEFS.items() if s in tracked}

    if "repeat_hire_rate" in tracked:
        known_clients = [j.get("client_id") for j in jobs if j.get("client_id")]
        if known_clients:
            clients = Counter(known_clients)
            signals["repeat_hire_rate"] = sum(
                count >= 2 for count in clients.values()
            ) / len(clients)

    if "average_rating" in tracked:
        # average_rating is a mean of 1-5 values, not a predicate-based rate.
        # Normalized to [0,1] here so NORMALIZERS can treat it as identity.
        # signals["average_rating"] = sum(j["rating"] for j in jobs) / n / 5.0
        signals["average_rating"] = sum(float(job.get("rating") or 0) for job in jobs) / n / 5.0

    return signals, n


def validate_platform(tracked: set[str]) -> None:
    """
    A platform onboarding as a native/API source must supply all CORE signals.
    This does NOT apply to csv_upload imports, which are held to the separate,
    minimal schema in docs/schema_spec.md (job_id, date, status only) and never
    go through this check — see design_decisions.md and starting_rating() in
    scoring.py for how imported-only workers are handled instead.
    """
    missing = CORE - tracked
    if missing:
        raise ValueError(f"Platform cannot onboard: missing core signals {sorted(missing)}")
