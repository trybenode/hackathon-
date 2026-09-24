# Schema Spec

Two separate schemas, not one shared one. Native jobs (done on our platform) and
imported jobs (brought in from outside) are structurally different, because outside
platforms can only realistically give us a fraction of what we can verify ourselves.

## Native job schema (`CommonJob`)

Full schema — everything available, because we control the data end-to-end.

| Field | Type | Required? | Notes |
|---|---|---|---|
| `job_id` | string | Yes | Unique per (worker, source_platform) |
| `date` | date | Yes | Drives future recency features, if ever added |
| `status` | enum: `completed` / `cancelled` / `no_show` | Yes | Drives completion/cancellation/no-show rates |
| `cancelled_by` | enum: `worker` / `client` / `platform` | Conditional — required if `status == "cancelled"` | Client/platform-caused cancellations are excluded from scoring; only worker-caused ones count against the worker |
| `dispute_resolution` | enum: `open` / `upheld` / `dismissed` | Yes for native jobs | Feeds `dispute_rate` |
| `client_id` | string | Optional | Needed only for `repeat_hire_rate` |
| `source_platform` | string | Yes | e.g. `"native"` |
| `import_method` | enum: `native` / `api` / `csv_upload` | Yes | Always `"native"` for this schema |
| `verified` | bool | Yes | Always `True` for native jobs |
| `flags` | list of strings | Optional, default `[]` | Vertical-specific events — see `trust_scoring_flag_integrity.md` |

## Imported job schema — deliberately minimal

Realistic testing of what platforms actually make available (CSV export, screen-scrape,
self-service download) showed the full schema is not achievable. Most platforms don't
expose `cancelled_by`, `dispute_resolution`, or `client_id` at all through any export a
worker could realistically get. So the import schema only asks for what's reliably
there:

| Field | Type | Required? |
|---|---|---|
| `job_id` | string | Yes |
| `date` | date | Yes |
| `status` | enum: `completed` / `cancelled` / `no_show` | Yes |

**Imported jobs never carry:** `cancelled_by`, `dispute_resolution`, `client_id`, or
`flags`. Not optionally-hoped-for, not sometimes-available — never expected at all. This
means imported history can only ever feed `completion_rate` and `cancellation_rate` (not
even `dispute_rate`, since `status` alone doesn't tell us about disputes).

## What this means for scoring

Because imported jobs can only supply two weak signals, they never go through the full
`score_worker` formula. Instead, imported-only workers get a separate `starting_rating`
(capped at 0.65, labeled "Building History (imported)"), computed only from
`completion_rate` and `cancellation_rate`, and structurally kept apart from the real
`band`/`decision`/`confidence` output of `score_worker`. Note: outside platforms don't
have an API for us to pull verified history automatically, so the realistic import path
is a worker uploading their own exported file — which they could edit before handing it
over. We're not solving that tampering risk with code; `starting_rating`'s cap and
"unverified" label exist specifically to account for it, not eliminate it.

## What's deliberately not in either schema

- Anything vertical-native (trip distance, item value, service category) — stays in the
  normalisation layer, never reaches the scoring engine.
- `late` as a flag or column — removed from the design entirely (see
  `trust_scoring_signal_definitions.md`).
