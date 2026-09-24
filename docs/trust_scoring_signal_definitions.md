# Signal Definitions

Every signal the scoring engine can use, which verticals can actually produce it, and
which tier it belongs to.

✓ = native (the platform naturally has this data)
~ = needs mapping in the normalisation layer (data exists but under a different name/shape)
✗ = doesn't really exist for this vertical

| Signal | Domestic | Handyman | Ride-hailing | Logistics |
|---|---|---|---|---|
| `completion_rate` | ✓ | ✓ | ✓ (trip completion) | ✓ (delivery success) |
| `cancellation_rate` | ✓ | ✓ | ✓ | ✓ |
| `dispute_rate` | ✓ | ✓ | ~ (called "complaints") | ~ (claims) |
| `no_show_rate` | ✓ | ✓ | ~ (becomes a cancellation after accept) | ~ |
| `repeat_hire_rate` | ✓ | ✓ | ✗ (matching is algorithmic) | ~ (B2B recurring only) |
| `safety_incident_rate` | ✓ | ~ | ✓ | ~ |
| `rework_rate` | ✗ | ✓ | ✗ | ✗ |
| `damage_report_rate` | ✗ | ~ | ✗ | ✓ |

`late_rate` was removed from the design entirely — without a scheduled/agreed time
captured at booking, there's no reliable way to know who was late (worker, client, or
neither), so it was dropped rather than kept as an unreliable signal. Worker unreliability
about showing up is still captured indirectly through `cancellation_rate`.

## Three tiers

**Core** (`completion_rate`, `cancellation_rate`, `dispute_rate`) — every vertical can
produce these. They're the portable currency for credentials. A native platform must
supply all three to onboard (`validate_platform` enforces this). Imported (CSV) sources
are held to a lower bar — see `trust_scoring_schema_spec.md`.

**Common but optional** (`no_show_rate`, `repeat_hire_rate`) — most verticals can produce
these, but not all, and their absence doesn't block scoring — the engine's coverage and
confidence mechanism handles missing optional signals gracefully.

**Vertical-specific** (`safety_incident_rate`, `rework_rate`, `damage_report_rate`) —
exist only where they mean something. Carried via the `flags` field on a job (see
`trust_scoring_flag_integrity.md`), not their own dedicated columns.

The engine itself doesn't change per vertical — only the `PlatformConfig` (weights and
required signals) and the vertical's own flag-to-signal mapping differ.
