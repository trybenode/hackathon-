# Railway / Render deployment

This repository provides buildable containers and production guards. It has not
been deployed to a production account. Use a staging environment first; service
creation and disk/compute plans can incur charges. Existing registration and
email-code sign-in are unchanged.

## Architecture and current limits

Deploy two containers: Next.js frontend and FastAPI backend, plus managed
PostgreSQL (existing Neon is supported) and Redis. The browser calls `/api/v1`
on the frontend HTTPS origin; the server proxy forwards cookies, idempotency
keys and approved request headers to the backend. This avoids cross-site
session-cookie failures between distinct provider domains. Secrets stay
server-side. Public verification SSR calls the backend privately.

The backend launcher runs one API process and optionally a separate durable
history worker process. Both share `/var/lib/trust/history` on the backend's
persistent disk. The worker reports a local heartbeat; readiness checks DB,
Redis and that heartbeat. **Keep one backend instance**: filesystem-backed audio
is not ready for independent replicas or separate remote worker services. A
shared object-storage design is required before scaling those workloads.
Disk-attached deploys can interrupt service; plan a short maintenance window.
Render rejects an explicit `maxShutdownDelaySeconds` on disk-attached services;
the blueprint omits it and uses Render's default shutdown behavior. Schema-only
validation does not establish all provider service/disk compatibility rules.

The container entrypoint initializes the disk directory, then drops to UID/GID
10001 with no new privileges for API/worker/migration commands. Only
`/var/lib/trust/history` is initialized; use this path and mount its parent.
Frontend runs as the Node image's unprivileged user. Images contain no dotenv
files or local credentials. Pin tested image digests in your release system;
base tags are updated by rebuilding, not by changing a running container.

## Required configuration

See [example variables](../deploy/production.env.example). Configure environment
variables in the provider secret manager, not tracked files. Production startup
refuses default database URLs, short/placeholder signing/proxy secrets, insecure
frontend/CORS origins, development email logging and shared platform API keys.
Use `ENVIRONMENT=staging` for staging with the same safeguards.

- `DATABASE_URL`: managed PostgreSQL async-compatible URL; use TLS for public
  connections. Neon `postgresql://...?...sslmode=require` is normalized by the app.
- `MIGRATION_DATABASE_URL`: **direct, unpooled** PostgreSQL connection for migration
  jobs. Use a migration role with schema permissions. The runtime DB role should
  have only application permissions. The migration runner falls back to
  DATABASE_URL if omitted; do not omit it when the application uses a transaction
  pooler, because the migration coordination uses session advisory locks.
- `REDIS_URL`: private-network Redis or authenticated `rediss://` for public
  endpoints. Redis failure deliberately blocks limited operations.
- `CREDENTIAL_SIGNING_SECRET`: at least 32 random characters. Generate each
  secret separately with `openssl rand -hex 32`. Keep the signing key stable;
  replacing it invalidates bundles signed with the previous key.
- `INTERNAL_PROXY_SECRET`: another random secret, identical on frontend/backend.
  This authorizes server IP forwarding, **not worker/customer authentication**.
- `RESEND_API_KEY` and `RESEND_FROM`: working transactional email with a verified
  sending domain; the shared onboarding sender is rejected in production.
- `FRONTEND_BASE_URL` and `CORS_ORIGINS`: exact frontend HTTPS origin without a
  trailing slash, e.g. `https://your-app.onrender.com`. Add only approved origins.
- `SMS_PROVIDER=disabled` initially, or `twilio` with the three existing Twilio
  variables after delivery testing. Disabled informal-contact confirmation
  fails honestly; native account-to-job matching is still separate.
- `RUN_HISTORY_WORKER=true`, `HISTORY_AUDIO_DIR=/var/lib/trust/history`: ensure the
  persistent volume is mounted at `/var/lib/trust`. Keep AI/speech disabled until
  their provider-specific acceptance checks pass. The worker still expires old
  private files when optional generation is off.

Frontend settings:

- **Build:** `NEXT_PUBLIC_API_BASE_URL=/api/v1` (Dockerfile default). Public values
  are inlined into bundles. Rebuild if you change this.
- **Runtime:** `API_PROXY_ORIGIN=http://<private-backend-host>:<port>` or Render's
  `API_PROXY_HOSTPORT` service reference. Neither value goes into browser code.
- **Runtime:** matching `INTERNAL_PROXY_SECRET`.
- `PROXY_TRUSTED_HOPS`: default **0**, which ignores forwarded addresses. Before
  public release, inspect your managed ingress's forwarding chain using staging
  probes; configure the number of trusted proxies counted from the right.
  Use 1 only when the final X-Forwarded-For entry is established as the actual
  browser peer. The proxy then parses that address and authenticates it to the
  API. Never enable forwarding when callers can reach Next.js directly or your
  ingress preserves a caller-controlled tail. Verify a spoofed incoming header
  does not evade the per-IP limiter. At 0, callers share proxy IP buckets: this is
  safe from spoofing but unsuitable for multi-user production traffic.

The API ignores arbitrary X-Forwarded-For; Uvicorn proxy-header trust is disabled.
Only authenticated proxy forwarding can override the rate-limit address.
Session-backed production mutations require an allowed Origin. CLI requests
carrying session cookies must supply that frontend Origin too.

## Render

1. Review [render.yaml](../render.yaml), link the intended branch and create a
   staging Blueprint in your Render account. The blueprint uses paid private
   API/web/disk/Redis resources in one region. It deliberately disables automatic
   deploys; do not point at a branch missing the implementation files.
2. Supply the database URLs, real frontend origin, email sender/key and other
   requested secrets. The blueprint generates signing/proxy secrets and shares
   only the proxy secret with the frontend. Do not paste secrets into PRs.
3. Render runs `python -m scripts.migrate_production` as the API pre-deploy command.
   Back up the database first. It serializes migration jobs with an advisory lock
   and runs `alembic upgrade head`; existing revisions remain unchanged.
4. Mount the API disk at `/var/lib/trust`, keep one instance and deploy the backend
   before the frontend. `/health` on the frontend checks backend readiness. The
   private-service blueprint does not use the web-only `healthCheckPath` field;
   monitor `/api/v1/health/ready` via the private network or frontend proxy.
5. Set the final frontend origin once Render allocates its public hostname, then
   redeploy the backend. Verify HTTPS, session cookies, proxy-IP behavior, loading
   errors and all enabled journeys. Use a verified custom domain if desired.

Render service references supply the private API host/port. No Caddy or public
backend port is needed for the supplied blueprint. Third-party webhooks can use
`https://<frontend>/api/v1/webhooks/payscrow` when payment is configured and
validated; the proxy preserves the existing signature/timestamp/delivery headers.
Platform API callers can use the same frontend `/api/v1/platform/...` gateway.

## Railway

1. Create frontend/backend services from this repository; set each service config
   file to `deploy/railway.frontend.json` or `deploy/railway.backend.json` in Railway
   settings. These files select Dockerfiles, migration commands and health checks.
   Keep repository root as
   build context. Select `frontend/Dockerfile` and `backend/Dockerfile` respectively
   (Railway's `RAILWAY_DOCKERFILE_PATH` variable can select each).
2. Add PostgreSQL/Neon and Redis, attach a backend volume at `/var/lib/trust`, and
   supply the same settings above. Connect the frontend to the backend over
   Railway private networking using `API_PROXY_ORIGIN` with the actual backend
   port. Backend listens on injected `PORT` (default 8000); frontend standalone
   also respects injected PORT.
3. Set the backend pre-deploy command to `python -m scripts.migrate_production`.
   Use the direct migration URL, and ensure both migration/API settings reach the
   same database. The migration step needs no mounted audio files.
4. Generate the frontend HTTPS domain; keep backend private for browser flows.
   Set frontend health path `/health` and backend `/api/v1/health/ready`. Keep one
   backend replica. Verify the ingress forwarding chain before setting trusted
   hops. Do not trust arbitrary forwarded headers at Uvicorn.

## Preflight, rollout and recovery

Build images from the repository root before configuring managed services:

```sh
docker build -f backend/Dockerfile -t trust-api:local .
docker build -f frontend/Dockerfile -t trust-web:local .
```

docker run --rm --env-file .env.production
  trust-api:local python -m scripts.check_production

or

cd backend
ENVIRONMENT=production .venv/bin/python -m scripts.check_production

Run inside the configured backend container:

```sh
python -m scripts.check_production
python -m scripts.migrate_production
python -m scripts.check_production --online
```

The offline preflight reports only invalid field names. Online mode checks the
application migration head, Redis and disk permissions without creating accounts,
jobs, verification evidence or payment records. `/api/v1/health/live` checks the
process; `/api/v1/health/ready` is for traffic readiness. Dependency failures
return generic 503 responses. Worker failure causes the supervisor to terminate
both processes, allowing the provider to restart the deployment; monitor queue
age and error counters as well as process health.

Before production promotion: confirm backups and a restore test, run PostgreSQL
migration/schema and Redis regressions, build both images, use staging sessions
for credential import/export, share/revoke, permitted contact confirmation and
review eligibility, interrupt a request to check receipt recovery, and verify no
private messages/audio appear publicly. Check 360 px layouts and physical devices
before advertising low-cost-device support. Test real email delivery and quota.

Optional release gates remain explicit:

| Capability                    | Gate                                                                                                                                                                                                |
| ----------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Identity/liveness             | Existing providers are stubs; production calls return unavailable. Real provider integration is required.                                                                                           |
| Escrow/protected jobs         | No-key stand-in is blocked outside development. Configure and test real Payscrow plus signed webhooks before enabling money flows.                                                                  |
| Informal contact confirmation | Real Twilio Verify configuration and delivery testing.                                                                                                                                              |
| N-ATLAS processing            | HTTPS authenticated gateway, actual model access, extraction/translation review.                                                                                                                    |
| Spitch speech                 | Valid key/voice mapping; enabled languages must also appear in`HISTORY_SPEECH_REVIEWED_LANGUAGES` after human review. This configuration records your approval; it does not prove quality itself. |
| Worker localized copy         | Candidate dictionaries need native review; keep the existing candidate notice.                                                                                                                      |
| Public multi-user traffic     | Verified managed-ingress IP mapping, cookie/origin checks, abuse and rate-limit smoke tests.                                                                                                        |

Monitor dependency readiness, worker heartbeat/queue age, generic provider errors,
rate-limit failures, disk utilization and DB connections. Do not log login codes,
audio/text contents, identity numbers, cookies, keys or bearer-link URLs. Existing
Uvicorn redaction and frontend proxy log suppression are preserved; configure
provider HTTP logs to redact `/verify/*`, `/confirm-work/*`, `/api/v1/verification/*`
and `/api/v1/history-confirmations/*`, or disable URL logging for these paths.
Encrypt backups and exclude ephemeral audio from long-lived backups; the 24-hour
retention cannot be met by indefinitely retaining disk snapshots. Managed-disk
snapshots require their own retention/delete policy.

To roll back: restore the previous tested application images and compatible
configuration, preserve signing keys and user data, and keep the additive schema
unless a reviewed recovery plan requires otherwise. Do not automatically run
Alembic downgrades. Disable optional providers to contain a failure while keeping
original text/history. No cloud account, production database or public endpoint
was modified while preparing these files.

Sources: [Render Blueprint fields](https://render.com/docs/blueprint-spec),
[Render disks](https://render.com/docs/disks),
[Railway volumes](https://docs.railway.com/volumes),
[Next.js standalone output](https://nextjs.org/docs/app/api-reference/config/next-config-js/output).

Local proxy verification after building the frontend: `node scripts/check_proxy_smoke.mjs`.
This uses temporary local servers and fake upstream responses, not real accounts or providers.

Validation evidence is recorded in [history_validation.md](history_validation.md).
The 2026-10-11 run passed 282 PostgreSQL/Redis tests, all five migration paths,
frontend types/lint/language checks, standalone build and proxy smoke, backend
both container builds and combined readiness/proxy/privacy smoke checks,
backend migrations/preflight, native image processing, and both runtime
dependency audits. The Python 3.12 container schema matches the OpenAPI snapshot.
These are local development checks; staging delivery, backup recovery, ingress
configuration and browser/device/provider review still require acceptance.
