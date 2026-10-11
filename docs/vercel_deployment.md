# Vercel demo deployment

Deploy **two projects from the same repository**, with Neon PostgreSQL and
Upstash Redis. This replaces Render for the current demo; container configs
remain available. Vercel Hobby is for personal, non-commercial use; commercial
launch, reliable continuous processing and full voice need a separate plan.

## 1. Reserve projects and configure data stores

Create `trust-api` with Root Directory **backend**, Framework **FastAPI**, and
`trust-web` with Root Directory **frontend**, Framework **Next.js**. Do not deploy
the repository root as a single project or use the Docker startup command.
Backend uses Python 3.12; select Node.js 24.x for the frontend. Use their actual
allocated production domains below, not example names.

Use an isolated Neon database for the demo. Copy its pooled URL for `DATABASE_URL`
and direct/unpooled URL for `MIGRATION_DATABASE_URL`. Create an Upstash free Redis
database and use its **TLS Redis connection URL**, starting with `rediss://`.
The `https://` REST URL/token is not compatible with our existing Redis client.
External provider/account verification and free quotas remain provider policies.

## 2. Set project variables

Backend: use [vercel.backend.env.example](../deploy/vercel.backend.env.example).
Frontend: use [vercel.frontend.env.example](../deploy/vercel.frontend.env.example).
Enter values into each project's Settings → Environment Variables.

Generate separate signing/proxy secrets with `openssl rand -hex 32`. The proxy
secret must match in both projects; keep the credential signing secret stable
and backend-only. Configure a real Resend key and verified sender for sign-in.
Never enter secrets as `NEXT_PUBLIC_*` variables.

Backend `FRONTEND_BASE_URL` and `CORS_ORIGINS` are the frontend's exact HTTPS origin.
Frontend `API_PROXY_ORIGIN` is the backend's HTTPS origin, without `/api/v1`.
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

Deploy the backend, then frontend. Backend `/api/v1/health/ready` should return
`{"status":"ready"}`; frontend `/health` checks that backend too. Exercise email
sign-in, canonical worker record, JSON credential import/export, share/revoke
and authorized text history. Ineligible protected reviews must remain blocked.
Check cookie paths, same-origin POSTs, retry receipts and public-field exclusion.

Backend deployment protection can block the frontend's server-to-server calls.
For this intentionally public demo API, check project protection settings. Do
not disable protection on unrelated private projects. Keep application-level
authentication/API keys; never expose a protection bypass token in browser code.
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
