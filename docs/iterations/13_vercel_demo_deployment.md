# Vercel demo implementation plan

1. Stories: deploy the existing Next.js and FastAPI apps as two Vercel projects,
   using Neon and Upstash, with no Docker supervisor or persistent audio. Keep
   cookie authentication and the same-origin proxy. This is a non-commercial demo.
2. Impact: Vercel project configs, Python version/entrypoint metadata, serverless
   runtime setting, async database pool selection, docs and regression checks.
   Preserve container/local defaults, normalization and scoring weights.
3. Contracts: no new API or migrations. Serverless uses NullPool behind Neon
   pooling and refuses worker/AI/speech/timer settings that require continuous
   execution. Existing timed expiry/payment maintenance needs an external operator
   or scheduler; do not claim automatic maintenance in this demo profile.
4. Dependencies: Vercel Hobby accounts/project domains, Neon pooled/direct URLs,
   Upstash TLS Redis URL (not its REST endpoint), verified Resend sender, matching
   proxy secret, ingress verification and existing provider/review dependencies.
5. Sequence: runtime guards and pool selection; backend/frontend Vercel configs
   with bundle exclusions; explicit migration and domain setup guide; regression,
   frontend checks and configuration validation. No cloud resources or deploys.
6. Verify: serverless rejects background processing, never launches expiry loops,
   uses nonpersistent application connection pooling; container behavior remains
   unchanged. Verify schema, backend tests, frontend types/lint and proxy smoke.
   Actual Vercel build and deployed flows remain provider-side acceptance.
7. Rollout: isolated demo database, manually coordinated migrations, stable public
   domains and environment secrets. No opportunistic migrations in cold starts.
   Disable preview deployment protection only where deliberately needed for API
   calls; never publish keys. Paid/commercial/full voice hosting remains separate.

Completion evidence: SQLite 285 passed/5 skipped; PostgreSQL/Redis 290 passed;
frontend types/lint and proxy smoke passed. Serverless readiness/preflight/no-worker
smoke passed locally; official Vercel config constraints and TOML parsed. CI
includes serverless smoke. Cloud build and deployed browser/provider acceptance
remain operator gates; no accounts, projects or cloud data were changed here.
