# Flag Integrity Rule

A flag is only ever added to a job's `flags` list through a specific, purpose-built
action in the app — never inferred from a rating, review text, or general feedback.
Each flag type maps to its own distinct trigger:

| Flag | Triggered by | Trigger mechanism |
|---|---|---|
| `"safety"` | Client or worker | Dedicated "Report a safety issue" flow |
| `"rework"` | Client | Dedicated "Request rework" action, distinct from a low rating |
| `"damage"` | Client | Dedicated "File a damage claim" flow |

`"late"` was considered and dropped. Without a scheduled/agreed time captured at
booking, there's no reliable way to know who was late — worker, client, or neither,
since a time may never have been agreed at all. A worker who's unreliable about showing
up already shows up in `cancellation_rate` via worker-caused cancellations, so nothing
is lost by removing it.

## Rules

- A flag is only ever added through one of the dedicated actions above — never inferred
  from a star rating or free-text feedback.
- Every flag needs platform confirmation (evidence attached, or a quick admin review)
  before it's written to the job record. This stops a bad-faith client from damaging a
  worker's score by flagging jobs with no basis.
- Imported jobs never carry flags. Since imports only supply `job_id`, `date`, `status`
  (see `trust_scoring_schema_spec.md`), `flags` stays `[]` for every imported job,
  permanently.
- This spec is what the report/complaint UI flow needs to implement: three distinct
  trigger flows, each writing exactly one string into a job's `flags` list.

## How flags feed scoring

Each vertical's `PlatformConfig` decides which flag values it cares about and which
signal each maps to — e.g. `"safety"` in a job's flags feeds `safety_incident_rate`, but
only for verticals where that signal is defined (domestic, ride-hailing). A flag's
meaning stays consistent across verticals; only whether a given vertical tracks that
signal at all changes.

**Note on `safety_incident_rate` specifically:** this signal originally carried a
permanent hard-fail (any safety incident disqualified a worker forever, regardless of
job history). That rule was deliberately removed after review: because scoring uses
equal weighting across all jobs (no recency decay for this MVP), a single incident would
never age out of the rate calculation, making the disqualification effectively
permanent — which was too harsh and wasn't a decision made on purpose. Safety incidents
now weigh the score down heavily (the highest weight in the domestic preset, 0.30) but
don't permanently disqualify. A worker can recover as clean jobs accumulate and dilute
the rate. Worth revisiting later: whether some safety incidents (e.g. confirmed
violence) should still be an unforgivable disqualifier while others (e.g. a single
unresolved complaint) shouldn't — currently every safety flag is treated identically.
