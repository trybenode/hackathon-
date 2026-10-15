Signal Definitions

Every signal the scoring engine can use, which verticals can actually produce it, and which tier it belongs to.

✓ = native (the platform naturally has this data) ~ = needs mapping in the normalisation layer (data exists but under a different name/shape) ✗ = doesn't really exist for this vertical

Signal	Domestic	Handyman	Ride-hailing	Logistics
completion_rate	✓	✓	✓ (trip completion)	✓ (delivery success)
cancellation_rate	✓	✓	✓	✓
dispute_rate	✓	✓	~ (called "complaints")	~ (claims)
no_show_rate	✓	✓	~ (becomes a cancellation after accept)	~
repeat_hire_rate	✓	✓	✗ (matching is algorithmic)	~ (B2B recurring only)
safety_incident_rate	✓	~	✓	~
rework_rate	✗	✓	✗	✗
damage_report_rate	✗	~	✗	✓
average_rating	✓	✓	✓	✓

Every job carries a rating (confirmed — not optional the way some other fields are), so average_rating is available across all verticals. Unlike the other signals, it's a mean of a 1–5 value rather than a rate over a predicate — aggregate() computes it separately and normalizes it to [0,1] before it reaches NORMALIZERS.

average_rating is now actively weighted in the domestic preset (0.15), not just calculated — for a while it was computed but had no actual effect on the score, since no preset's weights included it. That's fixed as of the domestic weight rebalance: ratings now genuinely influence the trust score, not just get recorded.

late_rate was removed from the design entirely — without a scheduled/agreed time captured at booking, there's no reliable way to know who was late (worker, client, or neither), so it was dropped rather than kept as an unreliable signal. Worker unreliability about showing up is still captured indirectly through cancellation_rate.

Three tiers

Core (completion_rate, cancellation_rate, dispute_rate) — every vertical can produce these. They're the portable currency for credentials. A native platform must supply all three to onboard (validate_platform enforces this). Imported (CSV) sources are held to a lower bar — see schema_spec.md.

Common but optional (no_show_rate, repeat_hire_rate, average_rating) — most verticals can produce these, but their absence doesn't block scoring — the engine's coverage and confidence mechanism handles missing optional signals gracefully. "Optional" here means a platform doesn't have to supply it to onboard, not that it carries no weight — average_rating (0.15) and repeat_hire_rate (0.10) both actively factor into the domestic preset's score when present.

Vertical-specific (safety_incident_rate, rework_rate, damage_report_rate) — exist only where they mean something. Carried via the flags field on a job (see flag_integrity.md), not their own dedicated columns.

The engine itself doesn't change per vertical — only the PlatformConfig (weights and required signals) and the vertical's own flag-to-signal mapping differ.
