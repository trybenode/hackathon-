# Decision: Disputes stay a separate field, not a status value

## The question
Should `status` become a 4-value field (`completed` / `cancelled` / `no_show` /
`disputed`), matching the early `/outcomes` API draft — or should disputes stay a
separate field (`dispute_resolution`) that can coexist with any status, as the current
schema already has it?

## Decision
Keep disputes as a separate field. No change to the existing schema.

## Reasoning
A dispute isn't a replacement for what happened to a job — it's a claim layered on top
of what happened. A job can be:
- Completed, then disputed afterward (work was done, client contests quality)
- Cancelled, then disputed (disagreement over whose fault the cancellation was)
- Rarely, even a no-show can be disputed (worker claims they did show up)

If `disputed` were its own status value, the record would lose what actually happened
underneath the dispute — a disputed-completion and a disputed-cancellation are very
different signals, but would look identical if collapsed into one status. It would also
skew `completion_rate`: a job that genuinely was completed, then later contested, would
stop counting as completed the moment a dispute opens, even though the work happened.

Keeping `status` and `dispute_resolution` independent preserves both facts: what
happened, and whether it's contested. This also matches `db.md`'s own design, which
models disputes as a separate `disputes` table linked to `jobs` — a related event, not a
replacement for the job's outcome status.

## What this means going forward
- No changes needed to `trust_scoring_schema_spec.md` or `signals.py` — the existing
  design (separate `dispute_resolution` field) was already correct.
- The `/outcomes` API doc's `disputed` status value is treated as an early draft
  written before the fuller schema existed, not a deliberate decision to follow instead.
- When building the Outcome Normalization pipeline, any source that represents disputes
  as a status value (rather than a separate flag) needs to be mapped: a `disputed`
  status from a raw source should map to whatever the underlying status actually was
  (completed/cancelled/no_show), with `dispute_resolution` set separately — not passed
  through as its own status.
