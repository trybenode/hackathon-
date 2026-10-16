# Vercel demo deployment

Deploy **one project with backend and frontend services**, with Neon PostgreSQL and
Upstash Redis. This replaces Render for the current demo; container configs
remain available. Vercel Hobby is for personal, non-commercial use; commercial
launch, reliable continuous processing and full voice need a separate plan.

## 1. Reserve projects and configure data stores

Import the repository with Root Directory **repository root**. The root
`vercel.json` builds `backend` (FastAPI, Python 3.12) and `frontend` (Next.js,
Node.js 24.x) independently. Per-directory configs remain standalone fallbacks.
Do not use the Docker startup command. Services are currently beta.

Public traffic goes to frontend, including `/api/v1`, where the existing proxy
preserves cookies and trusted headers. Backend remains internal. Frontend has a
`BACKEND_URL` binding to backend; Vercel injects it into runtime functions. Do not
set that variable manually or use it in builds or middleware. Public SSR and
readiness use the same resolver. Confirm names, visibility and binding before
release; no direct backend public rewrite is configured.

Use an isolated Neon database for the demo. Copy its pooled URL for `DATABASE_URL`
and direct/unpooled URL for `MIGRATION_DATABASE_URL`. Create an Upstash free Redis
database and use its **TLS Redis connection URL**, starting with `rediss://`.
The `https://` REST URL/token is not compatible with our existing Redis client.
External provider/account verification and free quotas remain provider policies.

## 2. Set project variables

Backend: use [vercel.backend.env.example](../deploy/vercel.backend.env.example).
Frontend: use [vercel.frontend.env.example](../deploy/vercel.frontend.env.example).
Enter both sets into the single project's Settings → Environment Variables.

Generate separate signing/proxy secrets with `openssl rand -hex 32`. The proxy
secret is configured once in the shared project; keep the credential signing
secret stable. Project environment variables are shared across services. Configure a real Resend key and verified sender for sign-in.
Never enter secrets as `NEXT_PUBLIC_*` variables.

`FRONTEND_BASE_URL` and `CORS_ORIGINS` are the single project's exact HTTPS origin.
Remove manual `API_PROXY_ORIGIN` and `API_INTERNAL_BASE_URL` overrides for this profile.
Set `NEXT_PUBLIC_API_BASE_URL=/api/v1` at build time. Enable Corepack with
`ENABLE_EXPERIMENTAL_COREPACK=1` so the frontend uses its pinned pnpm version.
Keep the normal `pnpm build` command. No rewrites bypassing our API proxy are needed.

`VERCEL=1` automatically selects serverless mode, but set `DEPLOYMENT_MODE=serverless`
explicitly for clarity. Keep `RUN_HISTORY_WORKER=false`, `HISTORY_AI_ENABLED=false`,
`HISTORY_SPEECH_ENABLED=false`, and `EXPIRY_SWEEP_SECONDS=0`. Startup rejects unsafe
serverless configuration, including development mode. Database connections use
NullPool, with Neon doing the upstream pooling.

Review Vercel's forwarding headers/ingress before changing `PROXY_TRUSTED_HOPS`.
At 0, requests through the proxy share rate-limit buckets. This remains a public
multi-user release gate; do not guess a trusted-hop count.

## 3. Apply migrations explicitly

Use a private, untracked `.env.vercel-demo` populated with the backend example
and the intended isolated demo database. From repository root:

```sh
docker build -f backend/Dockerfile -t trust-api:local .
docker run --rm --env-file .env.vercel-demo \
  trust-api:local python -m scripts.check_production
docker run --rm --env-file .env.vercel-demo \
  trust-api:local python -m scripts.migrate_production
```

Confirm the target and back up valued records before migrations. This operator
step uses the direct database URL and coordinated Alembic runner. Never migrate
during a Vercel build, cold start or ordinary API request. Repeat before later
schema-changing releases. No deployed function needs migration permissions.

## 4. Deploy and check

Deploy the project from repository root. Public `/api/v1/health/ready` should return
`{"status":"ready"}`; frontend `/health` checks that backend too. Exercise email
sign-in, canonical worker record, JSON credential import/export, share/revoke
and authorized text history. Ineligible protected reviews must remain blocked.
Check cookie paths, same-origin POSTs, retry receipts and public-field exclusion.

Deployment protection applies to the shared public surface. Internal backend calls
use the binding. Keep existing application authentication and API keys.
Use stable production domains. Configure separate database/settings for Preview
if enabled; do not allow every `*.vercel.app` origin or point previews at valued
production data. Environment edits require redeployment; public build variables
require rebuilding the frontend.

## Feature boundaries and maintenance

Text records, sharing, credentials and static page dictionaries remain supported
with their existing provider/evidence prerequisites. No persistent local files,
N-ATLAS model hosting, translated audio or continuously running worker are provided.
The function bundle excludes local env files, models, tests and operator scripts.

Timed guarantor expiry and payment reconciliation previously ran in a continuous
loop. This profile disables that loop: **an external scheduler/operator must run
the existing maintenance logic** before claiming automatic lifecycle processing.
Timestamp checks on public links/sessions still apply, but do not establish that
all timed business transitions were persisted. Do not advertise full unattended
guarantor/escrow operation based on this demo. Identity/payment stand-ins remain
unavailable in production; no evidence is fabricated.

Backend/Redis limits, function payload/duration/bundle limits, email quotas and
Hobby restrictions apply. Heavy model hosting is separate from web deployment.
Actual Vercel builds and deployed browser journeys remain acceptance gates:
local tests/config validation do not establish a successful cloud deployment.

Sources: [FastAPI on Vercel](https://vercel.com/docs/frameworks/backend/fastapi),
[Python runtime](https://vercel.com/docs/functions/runtimes/python),
[package managers](https://vercel.com/docs/package-managers),
[Hobby restrictions](https://vercel.com/docs/plans/hobby).

## Local services verification

Run `vercel dev -L` from repository root (or `vercel dev` with a linked account).
Bindings are injected automatically. Supply disposable local database/Redis and
existing development provider settings; do not use production data. Verify
`/health`, `/api/v1/health/ready`, sign-in and worker/share flows. Local checks
cannot establish cloud routing or successful Vercel builds.

See [Services](https://vercel.com/docs/services) and
[bindings](https://vercel.com/docs/services/bindings).


Optional live AI architecture: [private S3 and external N-ATLAS jobs](natlas_deployment.md).
Keep the default flags off until that infrastructure passes acceptance. The
serverless API can now enable AI with explicit private-storage/external-worker
configuration; local workers and speech remain blocked in this profile.
