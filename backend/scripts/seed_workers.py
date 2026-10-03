"""
10-worker seed set.

Hand-built worker job histories spanning a realistic spread of outcomes,
run through the real aggregate()/score_worker() code. This is not a unit
test — it's a sanity check that the bands the formula produces actually
feel right to a human, which is a different kind of validation than
correctness testing.

Run: python scripts/seed_workers.py  (from backend/)
"""
from app.services.trust_scoring.signals import aggregate
from app.services.trust_scoring.scoring import score_worker, PRESETS, starting_rating


def make_jobs(n, status="completed", n_clients=8, rating=5, **overrides):
    return [{"job_id": f"j{i}", "client_id": f"c{i % n_clients}",
             "status": status, "rating": rating, **overrides}
            for i in range(n)]


def run(label, jobs, tracked, preset="generic", note=""):
    signals, n = aggregate(jobs, tracked)
    result = score_worker(signals, n, PRESETS[preset])
    print(f"{label:45} n={n:3}  band={result['band']:16} "
          f"decision={str(result['decision']):5}  confidence={result['confidence']}")
    print(f"    {result['explanation_summary']}")
    if note:
        print(f"    Note: {note}")
    print()
    return result


DOMESTIC_FULL = {"completion_rate", "safety_incident_rate", "dispute_rate",
                  "repeat_hire_rate", "no_show_rate", "cancellation_rate"}
GENERIC_FULL = {"completion_rate", "dispute_rate", "no_show_rate",
                 "repeat_hire_rate", "cancellation_rate"}


print("=" * 90)
print("10-WORKER SEED SET")
print("=" * 90)
print()

# 1. Clean, established domestic worker — should be clearly High.
jobs = make_jobs(40, n_clients=6)
run("1. Clean domestic worker, 40 jobs, 6 repeat clients",
    jobs, DOMESTIC_FULL, "domestic")

# 2. Decent but not great — a few disputes and no-shows, should land Medium.
jobs = make_jobs(30, n_clients=10)
jobs[0]["status"] = "no_show"
jobs[1]["dispute_resolution"] = "upheld"
jobs[2]["dispute_resolution"] = "upheld"
run("2. Domestic worker, 30 jobs, 1 no-show + 2 upheld disputes",
    jobs, DOMESTIC_FULL, "domestic")

# 3. Genuinely poor performer — many disputes, should land Low.
jobs = make_jobs(25, n_clients=15)
for j in jobs[:6]:
    j["dispute_resolution"] = "upheld"
for j in jobs[6:9]:
    j["status"] = "no_show"
run("3. Domestic worker, 25 jobs, 6 upheld disputes + 3 no-shows",
    jobs, DOMESTIC_FULL, "domestic")

# 4. Brand new worker — must be Building History, not a fabricated score.
jobs = make_jobs(1)
run("4. Brand new worker, 1 job",
    jobs, DOMESTIC_FULL, "domestic")

# 5. Safety incident on an otherwise strong history — heavily weighed down,
#    but recoverable (no permanent disqualification, per the removed hard-fail).
jobs = make_jobs(40, n_clients=8)
jobs[0]["flags"] = ["safety"]
run("5. Domestic worker, 40 jobs, 1 safety incident, otherwise clean",
    jobs, DOMESTIC_FULL, "domestic",
    note="Should be pulled down hard (safety is highest weight) but NOT auto-disqualified.")

# 6. Ride-hailing, strong performer — High.
jobs = make_jobs(50, n_clients=40)
run("6. Ride-hailing worker, 50 clean trips",
    jobs, {"completion_rate", "cancellation_rate", "dispute_rate"}, "ride_hailing")

# 7. Ride-hailing, under this vertical's min_jobs (10) — Building History.
jobs = make_jobs(6, n_clients=6)
run("7. Ride-hailing worker, only 6 trips (min_jobs=10)",
    jobs, {"completion_rate", "cancellation_rate", "dispute_rate"}, "ride_hailing")

# 8. Client-cancelled jobs should NOT count against the worker.
jobs = (make_jobs(40, n_clients=8)
        + [{"job_id": f"cx{i}", "client_id": "c9", "status": "cancelled",
            "cancelled_by": "client"} for i in range(15)])
run("8. Domestic worker, 40 completed + 15 client-cancelled (excluded)",
    jobs, DOMESTIC_FULL, "domestic",
    note="Should score identically to worker #1 — the 15 client cancellations are noise.")

# 9. Imported-only worker — should NEVER get a real band, only starting_rating.
imported_jobs = [{"job_id": f"i{i}", "date": "2026-08-01", "status": "completed"}
                  for i in range(35)]
imported_jobs += [{"job_id": f"ix{i}", "date": "2026-08-01", "status": "cancelled"}
                   for i in range(5)]
imp_signals, imp_n = aggregate(imported_jobs, {"completion_rate", "cancellation_rate"})
sr = starting_rating(imp_signals, imp_n)
print(f"9. {'Imported-only worker, 35 completed + 5 cancelled (no native jobs)':43} "
      f"n={imp_n:3}  starting_rating={sr['starting_rating']}")
print(f"    label={sr['label']!r}  verified={sr['verified']}")
print(f"    Note: Capped at 0.65 regardless of how clean the imported history looks.")
print()

# 10. Boundary case — near the domestic medium_t threshold (0.70).
jobs = make_jobs(40, n_clients=8)
for j in jobs[:5]:
    j["dispute_resolution"] = "upheld"
run("10. Domestic worker, boundary case near medium_t (0.70)",
    jobs, DOMESTIC_FULL, "domestic")

print("=" * 90)
print("Review each result above: does the band and explanation feel right")
print("for what actually happened to that worker? Flag anything surprising.")
print("=" * 90)
