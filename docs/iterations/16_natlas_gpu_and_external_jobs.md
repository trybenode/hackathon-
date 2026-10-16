# Real N-ATLAS integration: GPU gateway and external jobs

Confirmed: retain API/frontend on Vercel; private object storage and external jobs.
Hugging Face access is approved; no GPU host exists yet. No real inference can be
claimed until a host, models, storage and end-to-end acceptance are available.

Stories: a worker uploads private audio, external worker claims the persistent
PostgreSQL job, materializes audio, normalizes it and calls real N-ATLAS ASR plus
extraction. Worker edits/approves the draft. Messages retain originals alongside
translations. Failure never creates verified work or changes scoring.

Impact: existing model gateway, history draft worker, configuration/production
guards, capabilities and docs. Preserve unrelated staged changes and unresolved
frontend merges. Never touch normalization or authentication.

Design: private S3 history-audio/ UUID keys, encrypted uploads and 24-hour logical
expiry; bucket lifecycle must independently remove orphaned uploads. PostgreSQL
leases/idempotency remain the durable external job queue. No public media URL.
Serverless upload cap 3 MiB to leave multipart space beneath function limits.
Add optional capability metadata. No database migration is required.

Sequence: harden real inference gateway, private storage handoff, external-worker
serverless guard, deployment examples, live smoke tool, contract tests and docs.
Dependencies: GPU/driver, model permissions/revisions, private S3 lifecycle and
IAM, shared DB connection, worker media tools, TLS endpoints and domain review.

Verification: gateway auth/shape/media failures; storage isolation/bounds/cleanup;
voice lifecycle/scoring isolation regressions; serverless configuration; contracts.
GPU smoke must use an authorized real recording and retain honest model revisions.
Rollout: keep production flags off until storage, worker and GPU are tested. Revert
by disabling HISTORY_AI_ENABLED; retain manual history and existing saved claims.

## Acceptance evidence and unresolved dependencies

Final targeted run: 50 passed, 2 PostgreSQL-only cases skipped (SQLite). Covers
gateway authentication/strict outputs/chunked media, private storage handoff,
cleanup, history rules and external-worker production guards/capabilities.
Broader backend run before the last three added cases: 395 passed, 5 skipped,
2 failures in developer request-log route-prefix expectations. These paths were
not changed by this integration. VoiceCapture targeted ESLint passed. Frontend
typecheck remains blocked by existing merge markers in app/page.tsx,
app/worker/layout.tsx and app/worker/profile/Profile.tsx; they were preserved.
OpenAPI regenerated (105 paths), including audio_max_bytes. No cloud data was
accessed, no model weights downloaded, and no resources/keys/deployments created.
GPU build/live inference, actual S3 lifecycle/IAM, external worker, PostgreSQL/Redis
acceptance, browser flow and per-language quality evaluation remain release gates.
