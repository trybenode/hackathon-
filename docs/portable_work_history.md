# Portable work history: implementation and integration guide

This guide covers the restricted review system, worker credential UI, shareable
verification results, and consent-backed developer history APIs. Interactive
OpenAPI is served at `/docs`; JSON is available at `/openapi.json`. A checked-in
snapshot is `docs/openapi.json` (regenerate with the command below).

Schema generation uses the Pydantic version pinned in `backend/requirements.txt`.
Install those dependencies before regenerating the snapshot. HTTP 422's standard
description is fixed to `Unprocessable Content` across Python versions; custom
error descriptions are preserved. CI uses Python 3.12 and checks the generated
file against the committed snapshot.

## Product boundaries

Workers can carry evidence earned outside this service into participating
platforms. An imported claim is not automatically verified. A dedicated API key
identifies its submitting organization; it does not prove that a job happened.
Reviewed credentials with `can_attest` may attest that organization's own records.
Unreviewed submissions remain `self_declared`, stay outside verified trust
scoring, and use a separate capped starting-history indication.

The public result is a standard summary, not a full dossier. It contains a
shortened display name, role/Nigerian state or territory (never a street address), identity status, generic-policy
assessment, aggregate work counts, and active guarantor status. Detailed work
records, client identifiers, documents, provider references, review comments and
credential tokens are excluded. Identity and guarantor sandbox evidence is
labelled. A result does not activate insurance or escrow.

## Authentication and responsibilities

User routes use the existing HTTP-only `guarantor_session` cookie. Despite its
name, ownership is resolved from the session's user and linked worker/customer
records. These features do not modify email-code sign-in, account creation or
seeded-account login. Working browser access for workers/customers remains an
integration dependency for the Software Engineer. Tests supply isolated auth
fixtures, not production login bypasses.

Platform routes use `X-API-Key`, resolved to a hashed, revocable `PlatformKey`
bound to an organization. A grant must authorize the operation on the linked
worker. Keys are never sent to browser components. The old shared
`PLATFORM_API_KEY` is accepted only for development trust queries, never for
platform history APIs. Set `ENVIRONMENT=production` outside local demos.

An operator provisions keys after reviewing an organization:

```bash
cd backend
.venv/bin/python scripts/manage_platform_key.py issue ORGANIZATION_UUID
# Attestation authority requires separate review:
.venv/bin/python scripts/manage_platform_key.py issue ORGANIZATION_UUID --can-attest
.venv/bin/python scripts/manage_platform_key.py revoke KEY_UUID
```

Issuance prints the secret once. Store it securely; do not commit it or send it
through telemetry. There is no public endpoint that grants attestation authority.

## Endpoint reference

All paths below are relative to `/api/v1`. User mutation examples assume a valid
existing cookie supplied with `--cookie "$TRUST_COOKIE"`. Set `TRUST_API` to the
base URL, e.g. `http://localhost:8000/api/v1`.

| Method / path | Authorization | Result |
| --- | --- | --- |
| GET `/me/record` | Own worker session | Canonical private snapshot, stored score/confidence, credentials, bounded completed preview and public-summary preview. |
| GET `/me/record/history?page=1&size=20` | Own worker session | All verified/self-declared history, source labels and completion status. |
| GET `/me/worker/record?page=1&size=20` | Own worker session | Compatibility projection of the same domain snapshot; retains its original response shape. |
| GET `/me/client/jobs?page=1&size=20` | Hiring-customer session | Only jobs attributed to the signed-in customer; review entry point. |
| GET `/workers/{worker_id}/credentials/export` | Own worker session | Signed bundle and freshly assessed summary. |
| POST `/workers/{worker_id}/credentials/import` | Own worker session | Imported count and recalculated band. |
| POST `/me/worker/shares` | Own worker session | New seven-day summary link token, returned once. |
| GET `/me/worker/shares/operations/{operation_id}` | Own worker session | Creation receipt without its secret; unknown operation returns 404. |
| GET `/me/worker/shares?page=1&size=20` | Own worker session | Share metadata; tokens are not returned again. |
| DELETE `/me/worker/shares/{id}` | Own worker session | Idempotent revocation, 204. |
| GET `/verification/{token}` | Bearer link, no session | Live standard summary; 410 when expired/revoked. |
| GET `/me/worker/platforms?page=1&size=20` | Own worker session | Available integrating platform names. |
| POST `/me/worker/platform-grants` | Own worker session | Named-platform approval and one-time consent token. |
| GET `/me/worker/platform-grants/operations/{operation_id}` | Own worker session | Approval creation receipt without its secret. |
| GET `/me/worker/platform-grants?page=1&size=20` | Own worker session | Approval metadata and permissions. |
| DELETE `/me/worker/platform-grants/{id}` | Own worker session | Idempotent revocation, 204. |
| POST `/platform/worker-links` | Dedicated platform key + consent token | Canonical worker ID linked to the platform's external account. |
| POST `/platform/workers/{external_id}/history/import` | Platform key + current import permission | Atomic batch receipt. Requires `Idempotency-Key`. |
| GET `/platform/workers/{external_id}/history?page=1&size=20` | Platform key + current read permission | Paginated facts and provenance, excluding client identifiers. |
| POST `/trust/query` | Platform key + current read permission | Platform-specific assessment from verified stored evidence. |
| GET `/jobs/{job_id}/review-eligibility` | Hiring-customer session | Eligibility reasons and existing receipt. |
| POST `/jobs/{job_id}/review` | Eligible hiring-customer session | Review receipt. Requires `Idempotency-Key`. |

Paginated grant/history lists return `items`, `total`, `page`, `size`, `pages`;
size is 1–100. The compatibility worker-record endpoint returns `outcomes` and
`total_outcomes` for the requested page. The canonical endpoint keeps at most
20 verified completed outcomes in its preview; use `/me/record/history` for
all outcome statuses and provenance. Review comments are private and are not in receipts.

## Evidence semantics and compatibility

`/me/record` is the single browser contract. Both record routes use the same
builder, and public verification uses an explicit whitelist from that builder.
Public requests skip private history presentation and starting-history loading.
Private views retain the real stored model score and show evidence confidence
separately. Neither value is a probability or guarantee.

Identity uses the latest check, including later failures. Successful `stub`
checks are sandbox evidence. Stored generic identity results do not establish
separate NIN and BVN verification. Guarantor lifecycle states are preserved;
only Active with a future expiry and successful identity/liveness evidence
counts as supported active status; sandbox support is labelled separately. Both identity and liveness
checks must support the guarantor's real verification label.

History `status` is the work outcome; `completion_status` is separate:
`Client Confirmed` requires an attributable, non-future customer confirmation,
`Released` requires a stored released job, and off-platform records show
`Recorded work` or `Self-declared record`. No boolean default proves auto-release.
Missing ratings and unavailable repeat-hire/dispute metrics remain unknown/null.
`last_updated` is snapshot retrieval time; `assessment.assessed_at` is calculation time.
Credential trust-summary completion rate is nullable when there is no eligible evidence.

The teammate's normalizer remains unchanged. A shared scoring adapter restores
missing ratings, propagates signal availability, and reads explicit legacy raw
facts in batches. Default null disputes/empty flags do not establish absence;
ambiguous legacy disputed events do not establish completion. Old credential
payload defaults likewise cannot establish absence. New signed exports carry
resolved availability. Client references are namespaced by source for scoring.
Scoring weights are unchanged; fingerprint version 3 invalidates old cached
assessments. Legacy records may correctly move to Building History. ML review
of this behavior is a release gate.

## Credentials

The worker record is `/worker/profile/record`; the Import button is on
`/worker/profile/record/credentials`. Import accepts a JSON export file up to
1.5 MB or a pasted token, capped at 1,000,000 characters. The UI uses
`worker_upload` as transfer metadata; the signed original source remains
authoritative. File metadata is not trusted instead of the token. Unknown
request fields are rejected.

```bash
curl --cookie "$TRUST_COOKIE" "$TRUST_API/workers/$WORKER_ID/credentials/export" --output verified-work-history.json
curl --cookie "$TRUST_COOKIE" --json '{"credential_token":"SIGNED_TOKEN","source_platform":"Source platform"}' "$TRUST_API/workers/$WORKER_ID/credentials/import"
```

An import result resembles:

```json
{"worker_id":"WORKER_UUID","imported_outcomes":5,"new_band":"High","status":"success"}
```

A repeated import returns zero additional outcomes. Wrong-worker, malformed,
tampered and expired tokens return 422. A missing/short signing secret returns
503. `CREDENTIAL_SIGNING_SECRET` must be at least 32 characters. Bundles expire
in seven days and contain at most 1,000 outcomes; tokens are capped at 1,000,000
characters. This is a centrally trusted issuer, not independent DID/VC issuer
interoperability. Platforms do not receive the signing secret.

## Sharing and consent

The worker previews the standard summary before creating a public link. Links
show live evidence, expire after seven days, and can be revoked. Responses use
`Cache-Control: no-store` and `Referrer-Policy: no-referrer`; pages are noindex.

```bash
curl --cookie "$TRUST_COOKIE" -X POST "$TRUST_API/me/worker/shares"
curl "$TRUST_API/verification/$SHARE_TOKEN"
curl --cookie "$TRUST_COOKIE" -X DELETE "$TRUST_API/me/worker/shares/$SHARE_ID"
```

Public tokens are shown once; only hashes are stored. If creation's response is
lost, reconcile by operation identifier and revoke the unrecoverable link before
creating another. Both creation endpoints accept an optional UUID
`Idempotency-Key`; the UI always supplies one. Replaying the same operation
returns the existing grant with `token: null`; changed details return 409.
The operation lookup is worker-owned and never returns the secret. A 404
lookup allows retry with the original identifier. A 5xx/timeout remains
uncertain until reconciliation succeeds. Do not generate a new identifier
until the prior operation is resolved or its grant revoked. Revocation stops future retrieval, not recall of downloaded records.
Never log tokens, complete bearer URLs or cookie values. The backend redacts
verification paths in Uvicorn access logs. Configure the frontend host, CDN and
reverse proxy to redact `/verify/*` and `/api/v1/verification/*` paths as well;
Next.js development logging suppresses incoming `/verify/*` requests and truncates fetch URLs;
the app cannot control upstream logging.

Detailed access requires a named-platform approval. There are no mandatory
technical scope checkboxes in public sharing. The approval screen separately
explains reading history and adding historical evidence.

```bash
curl --cookie "$TRUST_COOKIE" --json '{"organization_id":"PLATFORM_UUID","permissions":["read_history","import_history"]}' "$TRUST_API/me/worker/platform-grants"
curl -H "X-API-Key: $PLATFORM_KEY" --json '{"external_worker_id":"their-worker-123","consent_token":"ONE_TIME_CONSENT_TOKEN"}' "$TRUST_API/platform/worker-links"
```

A grant lasts seven days and is bound to one named platform and one external
account. Renewals require a new worker approval. External IDs use letters,
numbers, dots, underscores or hyphens; linking by names/phone numbers is not
supported. Every request rechecks consent, permissions, expiry and revocation.

## Historical ingestion and two-platform exchange

```bash
curl -H "X-API-Key: $PLATFORM_KEY" -H 'Idempotency-Key: import-2026-001' --json '{"outcomes":[{"source_record_id":"job-51","occurred_at":"2026-10-01T12:00:00+01:00","status":"completed","dispute_resolution":null,"rating":4,"attest":false}]}' "$TRUST_API/platform/workers/their-worker-123/history/import"
curl -H "X-API-Key: $PLATFORM_KEY" "$TRUST_API/platform/workers/their-worker-123/history?page=1&size=20"
```

Limits: 100 records per batch, ratings 1–5, timezone-aware dates, and statuses
`completed`, `cancelled`, `no_show`. Attested cancellations require
`cancelled_by`. An explicit `dispute_resolution: null` records known absence of
a dispute; omitting that field leaves dispute evidence unknown. Optional
ratings, clients and quality flags retain their availability instead of
inventing zeros. Client IDs are namespaced/hashed and excluded from history
responses. Historical verification does not create native job/protection records
or permit restricted reviews. History pages include the authoritative source
identifier and its current organization name for a readable provenance label.

Deduplication uses worker + authoritative organization + source record ID.
Changing an existing source record returns 409, rather than silently overwriting
history. A matching idempotency key returns the original receipt; using the same
key for a different payload or worker returns 409. Batches commit atomically.
An unreviewed credential requesting `attest: true` gets 403.

The walkthrough script uses two different platform credentials and two worker
approvals; it checks that both external accounts resolve to the same worker:

```bash
cd backend
# Supply keys/approval tokens through environment variables, not source files.
.venv/bin/python scripts/platform_history_demo.py            # preview only
.venv/bin/python scripts/platform_history_demo.py --send     # sends fictional demo history
```

Required variables: `TRUST_API`, `PLATFORM_A_KEY`, `PLATFORM_B_KEY`,
`PLATFORM_A_CONSENT`, `PLATFORM_B_CONSENT`. Source A approves import/read; receiving
B approves read. Default demo history is self-declared. `--attest` requires A's
reviewed attestation authority. Use isolated demo records, never real people.

The receiving platform can assess the mapped canonical worker:

```bash
curl -H "X-API-Key: $PLATFORM_B_KEY" --json '{"worker_id":"CANONICAL_WORKER_UUID","platform_type":"generic","job_context":{"job_type":"cleaning","value_band":"low"}}' "$TRUST_API/trust/query"
```

## Restricted customer reviews

Customer entry is `/client/jobs`, populated only from attributed persisted jobs.
The review UI is `/client/jobs/{job_id}/review`. It does not create accounts. Eligibility
requires all of: active authenticated hiring customer (`Job.client_id`), successful
latest identity check, independent completed/released job, explicit confirmed
customer and worker records with correct user IDs, a verified completion-confirmed
completed outcome, no open/under-review dispute, funded held/released escrow with
provider reference and `cover_active`, matching positive micro-premium/insurance,
and a successful premium-payment operation.

The Software Engineer must supply `ProviderOperation` with
`entity_type="job"`, `entity_id=job.id`, `operation_type="premium_payment"`,
`status=SUCCEEDED`. Insurance must be active or historically expired with its
provider reference. Any failed/refunded escrow blocks eligibility. Legacy jobs
without explicit customer attribution remain ineligible. Identity stubs are
accepted only in development and labelled. Auto-release alone is insufficient.
Authoritative completion, dispute and protection writers must acquire the job
row lock before changing its eligibility records, coordinating with review
submission so concurrent changes cannot race the eligibility decision.

```bash
curl --cookie "$CUSTOMER_COOKIE" "$TRUST_API/jobs/$JOB_ID/review-eligibility"
curl --cookie "$CUSTOMER_COOKIE" -H 'Idempotency-Key: review-job-51' --json '{"rating":4,"comment":"Completed the agreed work."}' "$TRUST_API/jobs/$JOB_ID/review"
```

Ratings are integers 1–5; comments have a 2,000-character limit. There is one
immutable review per job. An identical idempotent replay returns the original
receipt; a second/new payload returns 409. Rating, review and audit commit
atomically, then the generic assessment refreshes. Review text is not a safety
flag. Existing scoring weights remain unchanged.

Redis atomically limits attempts to five/minute/user and thirty/minute/IP in fixed UTC-minute buckets. Database locking
limits successful submissions to ten/reviewer/rolling 24 hours. Configure
`REVIEW_USER_ATTEMPTS_PER_MINUTE`, `REVIEW_IP_ATTEMPTS_PER_MINUTE`,
`REVIEW_DAILY_LIMIT`; these must be positive. Redis failure returns 503 without
accepting the review. 429/503 carry `Retry-After`. IP accounting uses the request
client; deploy with trusted proxy settings and never trust arbitrary forwarded
headers. These controls reduce easy abuse; they do not eliminate collusion.

## Failure examples and weak networks

| Scenario | HTTP | Code / behavior |
| --- | --- | --- |
| No user session | 401 | `AUTH_REQUIRED` |
| Unknown API key | 401 | `AUTH_REQUIRED` |
| Legacy key at platform history API | 403 | `FORBIDDEN` |
| Missing/expired/revoked platform consent | 403 | `CONSENT_REQUIRED` / `CONSENT_EXPIRED` |
| Unreviewed attestation | 403 | `ATTESTATION_NOT_ALLOWED` |
| Invalid public token | 404 | `LINK_NOT_FOUND` |
| Expired/revoked public token | 410 | `LINK_UNAVAILABLE` |
| Different replay payload | 409 | `IDEMPOTENCY_CONFLICT` |
| Changed existing source facts | 409 | `SOURCE_RECORD_CONFLICT` |
| Ineligible review | 403 | `REVIEW_INELIGIBLE` plus reasons |
| Duplicate review | 409 | `REVIEW_EXISTS` |
| Rate/velocity limit | 429 | `REVIEW_RATE_LIMIT` / `REVIEW_VELOCITY_LIMIT`, `Retry-After` |
| Redis unavailable | 503 | `LIMITER_UNAVAILABLE`, `Retry-After` |
| Invalid request | 422 | `INVALID_INPUT`; validation never echoes private values |
| Invalid/tampered/expired/wrong-worker credential | 422 | `REQUEST_FAILED`; human-readable `detail` |

```json
{"detail":"Worker approval has expired or been revoked.","code":"CONSENT_EXPIRED"}
```

Public verification is server-rendered and avoids camera dependencies. Summary
JSON targets <20 KB uncompressed. Detailed records are paginated and responses
are compressed. Forms preserve drafts in memory; no sensitive persistent offline
cache or service worker is introduced. A lost review response is reconciled
through eligibility/receipt lookup before resubmission. Credential retries reuse
the same token and cannot duplicate history. A disconnected public page reports
that fresh verification is unavailable instead of displaying a cached approval.

Concrete successful and failed request examples are in [feature_examples.http](feature_examples.http).
The file uses placeholder secrets and identifies the expected result for each request.

## Local setup

Install backend dependencies with `python3 -m venv .venv` and
`.venv/bin/pip install -r requirements.txt` from `backend`. Copy the root
`.env.example` to `.env` and use `.env.local` for a local disposable PostgreSQL
connection. Start Redis with `docker compose up -d redis` from the repository
root. PostgreSQL must be provisioned separately; Compose currently provides Redis only.
Set `CREDENTIAL_SIGNING_SECRET` to a strong random secret of at least 32 characters.
Start the API with `.venv/bin/uvicorn app.main:app --reload` from `backend`.
Install the frontend with `pnpm install --frozen-lockfile`, then `pnpm dev`.
`NEXT_PUBLIC_API_BASE_URL` defaults to `http://localhost:8000/api/v1`; the public
SSR route can use `API_INTERNAL_BASE_URL` (including `/api/v1`) for server access.
Production frontend builds fetch the existing Google Fonts during compilation.

Existing worker/customer sessions, attributed jobs, and authoritative protection
records must be supplied by the Software Engineer. The fixture-driven acceptance
tests are reproducible without modifying sign-in. Redis is required for review
submission; the other flows use PostgreSQL.

## Validation and handoff

```bash
cd backend
.venv/bin/alembic upgrade head
.venv/bin/python scripts/check_migrations.py
# Creates/deletes its own temporary databases on the test server (CREATE DATABASE permission):
TEST_DATABASE_URL=postgresql+asyncpg://trust@localhost:5432/trust_test .venv/bin/python scripts/check_migration_paths.py
.venv/bin/pytest -q
# TEST_DATABASE_URL must point to a disposable test database: the suite resets it.
DATABASE_URL=postgresql+asyncpg://trust@localhost:5432/trust_test TEST_DATABASE_URL=postgresql+asyncpg://trust@localhost:5432/trust_test TEST_REDIS_URL=redis://localhost:6379/15 .venv/bin/pytest -q
.venv/bin/python scripts/export_openapi.py
cd ../frontend
pnpm typecheck
pnpm lint
pnpm build
# If Turbopack cannot bind its build-worker port in your environment:
pnpm exec next build --webpack
```

Coordinate shared-Neon migrations; do not run the test suite against that shared
database. The new merge revision preserves both existing branches; the subsequent
revision adds nullable worker-scoped grant operation identifiers. CI checks
upgrades from empty and from either previous head and compares the schema.
The combined feature release adds nullable customer/provenance columns and feature tables; existing authentication records and sign-in behavior are preserved.

Outstanding team responsibilities: authenticated worker/customer entry,
authoritative escrow/premium/completion/dispute records, reviewed platform
attestation issuance, Figma review, representative Android/network validation,
and real KYC/insurance provisioning. SMS/USSD, independent-issuer key discovery,
former-customer attestations, moderation/appeals operations and persistent offline
queues are not implemented. Correction conflicts remain explicit; they are not
resolved by silently replacing adverse history. Configure a worker support and
correction process before a real-user pilot.

Owner assignments, Figma requirements, and pending signoffs are recorded in
[integration_handoff.md](integration_handoff.md). Current verification evidence
is in [implementation_validation.md](implementation_validation.md).
