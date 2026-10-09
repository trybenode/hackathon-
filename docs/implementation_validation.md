# Weekly integration: validation and handoff

Validated on 8 October 2026 against main baseline `a3412d0` plus the integration
working tree. This replaces the previous branch-specific report. All database
fixtures were fictional and isolated in temporary local Docker PostgreSQL/Redis
services. No shared Neon migration, deployment, auth change or normalizer change
was performed. Existing unrelated local files were preserved.

| Check | Result |
| --- | --- |
| Full backend suite, SQLite | 163 passed; two PostgreSQL/Redis checks skipped |
| Full backend suite, PostgreSQL 16 + Redis 7 | 165 passed; no skips, including row-lock concurrency and Lua rate limits |
| Upgrade from empty PostgreSQL | Pass through `c735ab42f6d0`; migrated schema matches models |
| Upgrade from `1d7fe6fb9d97` | Pass; original revisions preserved, schema matches models |
| Upgrade from `8f41c20a9e37` | Pass; original revisions preserved, schema matches models |
| Alembic graph | One head, `c735ab42f6d0` |
| Frontend route types / TypeScript | Pass |
| Frontend ESLint | Pass |
| Production build | Pass with `next build --webpack`; sandboxed Turbopack cannot bind its worker port |
| OpenAPI snapshot | Generated from the combined app: 40 paths; cookie security includes canonical records and customer entry |
| Two-platform script over HTTP | Pass: fictional A imports five attested records; separately approved B reads and assesses them |
| Public verification over HTTP | 627 bytes uncompressed for fixture; GZip and privacy headers verified |
| Production public SSR | Summary is present without executing JavaScript; sandbox labelled; street address and MediaPipe excluded |
| Live revocation | API returns 410; next SSR response removes the worker summary |
| Backend access logs | Bearer paths display `[redacted]` |
| Git whitespace / protected files | Diff check passes; authentication and `normalisation.py` unchanged |

Business regressions cover canonical/compatibility agreement, bounded previews,
paginated all-status history, latest failed identity, sandbox labels, guarantor
expiry/lifecycle and verification support, nullable ratings/metrics, conservative
legacy evidence, explicit signal coverage, source-scoped clients, signed export
availability, source and tenant isolation, consent/revocation, grant-operation
ownership and idempotency, batch rollback, credential integrity/duplicates,
restricted-review protection/completion/dispute eligibility, review concurrency,
private comments/audit, daily velocity and real concurrent Redis attempt limits.

CI checks all three migration starting states, schema agreement, PostgreSQL/Redis
regressions and generated OpenAPI consistency. Synthetic before/after scoring
examples are in [scoring_comparison.json](scoring_comparison.json); these are for
ML review and do not establish approval of real-worker reassessments.

## Acceptance gates still pending

No connected browser surface was available. Interactive form behavior, 360 px
visual checks, Figma comparison, real interrupted-network interaction,
clipboard/WhatsApp and representative low-cost Android tests remain pending.
HTTP checks, responsive CSS and a build do not establish device support.

Software review remains required for customer browser access, authoritative
attribution/protection/completion/dispute writers, platform attestation approval,
shared migration/deployment coordination and upstream token redaction.
ML review remains required for conservative evidence eligibility and legacy
reassessment behavior; weights are unchanged and fingerprint version is 3.
UI/UX must supply frames and approve comparison. Docs/Presentation must reproduce
the walkthrough and review product claims.

Assignments and Figma requirements: [integration_handoff.md](integration_handoff.md).
API contracts and instructions: [portable_work_history.md](portable_work_history.md),
[feature_examples.http](feature_examples.http), [openapi.json](openapi.json).
