"""

Outcome Normalization

Converts raw job data from any source (native platform events, the /outcomes
API payload described in API_Schema.md, or imported files from outside
platforms) into the common job schema defined in
docs/trust_scoring_schema_spec.md, so trust_scoring.signals.aggregate()
never has to know or care where a job record originally came from.
"""

from app.models.domain import NormalizedOutcome

# Only flags our scoring engine actually knows how to use (see
# docs/trust_scoring_flag_integrity.md). "late" is deliberately excluded —
# it was removed from the design entirely. Any other flag value an outside
# source sends (e.g. "on_time") is silently dropped, not guessed at.
KNOWN_FLAGS = {"safety", "rework", "damage"}


def _filter_flags(raw_flags: list) -> list:
    """Pass through only the flag values SIGNAL_DEFS actually understands."""
    return [f for f in (raw_flags or []) if f in KNOWN_FLAGS]


def normalise_db_row(row: NormalizedOutcome) -> dict[str, object]:
    """Convert a persisted normalized outcome into the scorer's common job shape."""

    status = getattr(row.status, "value", row.status)
    return {
        "job_id": str(row.outcome_key),
        "date": row.occurred_at,
        "status": status,
        "cancelled_by": row.cancelled_by,
        "dispute_resolution": row.dispute_resolution,
        "client_id": row.client_id,
        "rating": float(row.rating or 0),
        "flags": _filter_flags(row.quality_flags or []),
        "source_platform": row.source_platform,
        "import_method": row.import_method,
        "verified": row.verified,
    }


# ---------------------------------------------------------------------------
# Native jobs: already close to canonical shape. This validates required
# fields and stamps provenance rather than transforming data.
# ---------------------------------------------------------------------------

def normalise_native(job: dict) -> dict:
    """
    Native jobs originate on our own platform and should already match the
    full CommonJob schema. Validates required fields are present and stamps
    provenance fields (source_platform, import_method, verified).
    """
    required = ("job_id", "date", "status")
    missing = [f for f in required if f not in job]
    if missing:
        raise ValueError(f"Native job missing required fields: {missing}")

    return {
        "job_id": job["job_id"],
        "date": job["date"],
        "status": job["status"],
        "cancelled_by": job.get("cancelled_by"),
        "dispute_resolution": job.get("dispute_resolution"),
        "client_id": job.get("client_id"),
        "rating": job.get("rating"),
        "flags": _filter_flags(job.get("flags")),
        "source_platform": "native",
        "import_method": "native",
        "verified": True,
    }


# ---------------------------------------------------------------------------
# /outcomes API payload (API_Schema.md): raw outcome events posted by
# platforms or the independent-job flow. outcome.status can be "disputed" —
# per docs/trust_scoring_decision_disputes_field.md, our schema never uses
# "disputed" as a status; a dispute is a fact layered on top of what
# actually happened, not a replacement for it. This function does that
# mapping.
# ---------------------------------------------------------------------------

def normalise_outcome_event(payload: dict) -> dict:
    """
    Maps a raw /outcomes API payload into a native job record.

    Known limitation: if a source reports status="disputed" with no further
    detail on the underlying outcome, we cannot recover whether the job was
    actually completed, cancelled, or a no-show. In that case we default the
    underlying status to "completed" with dispute_resolution="open", since a
    dispute over a job implies work was at least attempted — the more common
    real-world case (disputed quality of finished work) rather than a
    disputed cancellation. This is a documented assumption, not a certainty:
    revisit if a real source can supply the true underlying status alongside
    a dispute flag instead of overloading status entirely.

    client_id and cancelled_by are not present anywhere in the /outcomes
    payload as specified in API_Schema.md, so both are set to None rather
    than guessed. This means repeat_hire_rate cannot be computed from
    events ingested this way until the payload is extended, or a separate
    party lookup is added.
    """
    outcome = payload["outcome"]
    raw_status = outcome["status"]

    if raw_status == "disputed":
        status = "completed"
        dispute_resolution = "open"
    elif raw_status in ("completed", "cancelled", "no_show"):
        status = raw_status
        dispute_resolution = None
    else:
        raise ValueError(f"Unrecognised outcome status: {raw_status}")

    return {
        "job_id": payload["job_id"],
        "date": outcome["completed_at"],
        "status": status,
        "cancelled_by": None,  # not present in the /outcomes payload
        "dispute_resolution": dispute_resolution,
        "client_id": None,     # not present in the /outcomes payload
        "rating": outcome.get("rating"),
        "flags": _filter_flags(outcome.get("quality_flags")),
        "source_platform": "native",
        "import_method": "native",
        "verified": True,
    }


# ---------------------------------------------------------------------------
# Imported jobs: minimal schema only (job_id, date, status), per
# docs/trust_scoring_schema_spec.md. Each outside source needs its own
# status-vocabulary mapping — no two platforms name statuses the same way.
# ---------------------------------------------------------------------------

# One entry per known import source. Maps that source's raw status string to
# our status enum. Add a new key here for each new import source supported.
STATUS_MAPS = {
    "ridehailing_generic": {
        "COMPLETED": "completed",
        "DRIVER_CANCELED": "cancelled",
        "RIDER_CANCELED": "cancelled",
        "NO_SHOW": "no_show",
    },
}


def normalise_import(rows: list[dict], source_platform: str) -> list[dict]:
    """
    Maps raw rows from an imported source into the minimal import schema.

    Any row whose status doesn't map cleanly is skipped, not guessed at —
    silently guessing at an unmappable status would corrupt the signal
    rather than just being absent (same principle behind the original
    "missing signal defaults to 0, scores as perfect" bug this design
    already guards against elsewhere).

    Returns dicts matching the minimal import schema: job_id, date, status,
    source_platform, import_method="csv_upload", verified=False. Never
    includes cancelled_by, dispute_resolution, client_id, rating, or flags —
    imported jobs never carry these (see docs/trust_scoring_schema_spec.md).
    """
    if source_platform not in STATUS_MAPS:
        raise ValueError(f"No status mapping defined for source '{source_platform}'")

    status_map = STATUS_MAPS[source_platform]
    normalised = []
    for row in rows:
        mapped_status = status_map.get(row.get("status"))
        if mapped_status is None:
            continue  # unmappable status: skip rather than guess

        normalised.append({
            "job_id": row["job_id"],
            "date": row["date"],
            "status": mapped_status,
            "source_platform": source_platform,
            "import_method": "csv_upload",
            "verified": False,
        })
    return normalised


def merge_imported_sources(*sources: list[dict]) -> list[dict]:
    """
    Combines job records from multiple imported sources into one unified
    pool for a single worker, per the "unified starting_rating" decision —
    imports are never scored separately per source. Callers pass the output
    of one or more normalise_import() calls; this concatenates them.
    Deliberately trivial: the "unification" happens because aggregate() and
    starting_rating() run once on the combined list, not because this
    function does anything clever.
    """
    combined = []
    for source in sources:
        combined.extend(source)
    return combined
