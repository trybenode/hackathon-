"""Conservative scoring inputs; preserve the team's normalization contract."""
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.domain import Dispute, DisputeStatus, NormalizedOutcome, RawOutcome
from app.services.normalisation import normalise_db_row

FLAG_SIGNALS = {"safety": "safety_incident_rate", "rework": "rework_rate", "damage": "damage_report_rate"}


def scoring_input(row: NormalizedOutcome, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Restore missing values and infer legacy coverage only from reported facts.

    Explicit source null dispute_resolution means reported absence. A database
    default empty flag list or null dispute column alone does not mean absence.
    """
    item = normalise_db_row(row)
    item["rating"] = float(row.rating) if row.rating is not None else None
    payload = payload or {}
    source = payload.get("outcome", payload)
    source = source if isinstance(source, dict) else {}
    declared = getattr(row, "available_signals", None)
    available = set(declared) if declared is not None else set()
    status = item["status"]
    ambiguous_completion = source.get("status") == "disputed" and declared is None
    if ambiguous_completion:
        item["status"] = "unknown"
    known_outcome = not ambiguous_completion and (status in {"completed", "no_show"} or (status == "cancelled" and row.cancelled_by in {"worker", "client", "platform"}))
    if known_outcome:
        available.update({"completion_rate", "no_show_rate", "cancellation_rate"})
    else:
        available.difference_update({"completion_rate", "no_show_rate", "cancellation_rate"})
    legacy_credential = getattr(row, "normalization_version", None) == "credential-v1" and declared is None
    if row.dispute_resolution is not None or (not legacy_credential and "dispute_resolution" in source):
        available.add("dispute_rate")
    if row.client_id:
        available.add("repeat_hire_rate")
        # Client references are local to their authoritative source.
        item["client_id"] = f"{row.source_platform}:{row.client_id}"
    else:
        available.discard("repeat_hire_rate")
    if row.rating is not None:
        available.add("average_rating")
    else:
        available.discard("average_rating")
    for flag, signal in FLAG_SIGNALS.items():
        if flag in item["flags"] or (not legacy_credential and any(isinstance(source.get(key), list) for key in ("flags", "quality_flags"))):
            available.add(signal)
    if declared is not None:
        available.intersection_update(declared)
    item["available_signals"] = sorted(available)
    return item


async def scoring_inputs(session: AsyncSession, rows: list[NormalizedOutcome]) -> list[dict[str, Any]]:
    """Resolve legacy raw evidence and authoritative open disputes in batches."""
    raw_ids = {row.raw_outcome_id for row in rows if row.available_signals is None}
    payloads = dict((await session.execute(select(RawOutcome.id, RawOutcome.payload).where(RawOutcome.id.in_(raw_ids)))).all()) if raw_ids else {}
    job_ids = {row.job_id for row in rows if row.job_id is not None}
    open_jobs = set((await session.scalars(select(Dispute.job_id).where(Dispute.job_id.in_(job_ids), Dispute.status.in_([DisputeStatus.OPEN, DisputeStatus.UNDER_REVIEW])))).all()) if job_ids else set()
    result = []
    for row in rows:
        item = scoring_input(row, payloads.get(row.raw_outcome_id))
        if row.job_id in open_jobs:
            item["dispute_resolution"] = "open"
            item["available_signals"] = sorted(set(item["available_signals"]) | {"dispute_rate"})
        result.append(item)
    return result
