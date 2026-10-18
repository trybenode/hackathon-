# Additional verification and ownership-reviewed imports

## Behavior and trust boundaries

This pilot adds onboarding permission without altering verified assessment weights,
normalization, registration or sign-in. `decision`, `band`, `confidence` remain the
existing scorer's answers. An optional `onboarding` object appears on `/trust/query`,
`/me/record` and compatibility `/me/worker/record`. Legacy clients must continue
using their existing boolean until they explicitly adopt the new actions.

- Scoring rejection/disqualification stays declined; human review cannot override it.
- Missing **genuine** latest identity or liveness → `additional_verification`.
- Eligible Building History → `manual_review`; a submitted case has `REVIEW_PENDING`.
- Operations may approve **limited** first-party onboarding, request information,
  decline or revoke. A platform reviewer may also approve under its own enabled policy.
- Workers qualifying through verified scoring follow that policy. They acquire no
  invented historical outcomes. Approval changes permissions, never the trust band.
- First-party limited: **one active job, NGN25,000 maximum per job, 30 days**.
  Draft, Accepted, In progress, Submitted, Completed (unreleased), and Disputed count.
  Job creation and new escrow initiation check limits under the worker row lock.
  There is currently no price-change interface. Any future one must call the same gate.
  Existing funded work retains completion, dispute, release and settlement paths.
- External platforms must enforce returned restrictions on their own systems.
  Updating policy, changing evidence/checks, expiry, or revoking access invalidates
  stale permissions; re-query before starting new work. First-party policy is fixed.

**Ownership approved means “ownership reviewed; history unverified.”** It does not
prove the document genuine, customer confirmation or job completion. A matching
worker ID/name is only a consistency check. Operations must cross-check the private provider reference and compare the genuine
verified identity profile with document names, contact/account and job/source
references and record an ownership basis. Never fabricate genuine checks for a demo.
The existing provider seam must actually support live identity and liveness before
this approval journey can be released; stub/sandbox checks do not qualify.

## Setup and rollout

Apply the additive Alembic revision `a7d01e264c90` after `c5b96592228a` in a coordinated
maintenance/deployment step. Existing revisions are retained, with a single head.

```sh
cd backend
.venv/bin/python -m alembic heads
.venv/bin/python -m alembic upgrade head
```

Enable independently in a development/test environment first:

```dotenv
UNSIGNED_IMPORTS_ENABLED=true
ADDITIONAL_VERIFICATION_ENABLED=true
# Required for persistent rate limiting across API replicas:
REDIS_URL=redis://localhost:6379/0
# Required for production supporting evidence (private bucket, encryption):
S3_BUCKET=your-private-bucket
AWS_REGION=your-region
AWS_ACCESS_KEY_ID=your-server-key
AWS_SECRET_ACCESS_KEY=your-server-secret
# Optional HTTPS endpoint for S3-compatible storage:
AWS_ENDPOINT_URL_S3=
```

Keep storage credentials server-side. Reuse the existing S3 config; use a private
bucket/prefix policy limited to `ownership-review/*` for review file operations.
Require encryption, deny anonymous/public ACL access, and configure provider
backup/version retention to match the raw-file policy. Access needs PutObject,
GetObject, DeleteObject and prefix-scoped ListBucket for orphan cleanup. Production
has **no local-storage or discard-success fallback**. Development without S3 uses a
private local directory (0700, files 0600), optionally `OWNERSHIP_STORAGE_DIR`.
An unavailable storage/Redis service returns 503, never a fake successful upload.

Schedule at least hourly from an external trusted worker/operator environment:

```sh
cd backend
.venv/bin/python -m scripts.expire_review_evidence
```

Each run expires/deletes up to 100 due batches, then removes orphan objects older
than 30 days. Run more often if backlog exceeds 100/hour. Downloads stop immediately
at expiry even if deletion is waiting on storage recovery. Monitor scheduler failures,
deletion failures and overdue objects. Failed deletions are retried; access denial
does not mean physical deletion succeeded. Raw attachments expire 30 days after final
review; unreviewed submissions expire 30 days after preparation. Requests for more
information do not extend the unreviewed deadline. Approved derived rows, hashes,
review reasons and audit provenance remain; no identity numbers/documents are added
to public records. Define a separate organizational policy for minimal audit retention.
A database commit failure may leave an orphan, recovered by this scheduled cleanup.
Do not expose the cleanup CLI as an unauthenticated public endpoint.

Turning flags off disables new imports/reviews or onboarding enforcement independently;
existing auth, signed imports, trust scoring and settlement keep their behavior.
Do not roll back data tables after pilot evidence has been collected without an
approved retention/export procedure. No shared/cloud migrations were executed here.

## Roles and web journeys

Use existing signed-in accounts. No reviewer is inferred from developer or admin
presentation. Only a trusted operator with database access can assign a reviewer:

```sh
cd backend
.venv/bin/python -m scripts.manage_reviewers grant ops@example.com \
  --scope operations --operator operator@example.com \
  --reason 'Assigned to the pilot ownership and first-party onboarding queue'
.venv/bin/python -m scripts.manage_reviewers grant reviewer@example.com \
  --scope YOUR_ORGANIZATION_UUID --environment production \
  --operator operator@example.com --reason 'Assigned to tenant onboarding review'
# Repeat with `revoke` to remove a role; every change records operator and reason.
```

Worker: `/worker/profile/record/verification` → select intended platform → complete
existing identity/liveness journey → request review → read review status/reason →
reply when information is requested. Tenant review needs current `read_history`
consent and an authoritative platform-worker link. A worker can withdraw/correct
unsigned evidence separately; this never automatically approves onboarding.

Operations: `/review` → Ownership evidence → inspect profile/rows → download private
supporting file → explain the identity association and decide. First-party onboarding
is a separate tab/case/decision. Tenant reviewers: `/developer/reviews` or `/review`
with explicit organization/environment role → consented check/assessment summary →
onboarding decision. They cannot download ownership attachments, see identity provider references or see other tenants.
No reviewer can decide their own case or rewrite the assessment. Version/evidence
checks reject stale and concurrent decisions. Workers see in-app states and reviewer
reasons in the hub; this iteration does not add email/push notifications.

The new worker screens have typed English/Yoruba/Hausa/Igbo copy; candidate translations
are visibly marked. Language changes preserve selected files, consent, response,
preview and pending operation ID. Existing unrelated worker/auth screens are unchanged.

## Import classification and data

- Signed credential JSON/pasted token: use existing signed import. Preserve signature,
  expiry, issuer and worker-binding checks. Tampered/expired/wrong-worker credentials
  fail there; **never retry as unsigned automatically**.
- Unsigned history: CSV **and** PDF/JPEG/PNG supporting file; preview and explicit consent.
- Document alone: provide the CSV too. A visible signature on a PDF is not a signed credential.
- CSV up to **2 MiB / 1,000 rows**, supporting file up to **3 MiB**, uploaded separately.
  File signatures are checked and downloads are attachment-only octet streams with
  `nosniff`, restrictive CSP, no-store and explicit reviewer authorization. Signature
  checks are not document authenticity checks or malware certification.

Download `/me/history-imports/template`. Required columns `worker_id,job_id,date,status`;
optional `cancelled_by,source_reference`. UTF-8, ISO dates, unique job IDs; dates cannot
be future dates. Statuses: `completed`, `cancelled`, `no_show`, `unknown`. Cancellation
needs `worker`, `client`, or `platform` attribution. Unknown/missing signals stay unknown.
Every row must match the session worker UUID; authoritative WorkerLink external IDs
are accepted only for the named source `platform:ORGANIZATION_UUID`. Mixed-worker,
wrong-worker and contradictory files are rejected. Extra columns are rejected.

Submitted files/rows are immutable. Corrections prepare a new batch with `replaces_id`;
submitting it withdraws the old batch immediately. Approved rows deduplicate by worker,
source and source job ID; changed approved facts require explicit replacement.
Unsigned approval creates only `ProvisionalRecord`, never `NormalizedOutcome`.
The existing starting-history formula uses supported completion/worker-cancellation
facts and is capped at **0.65**. Unknown-only rows yield a null provisional rating.
Rejected, unresolved, withdrawn and superseded rows cannot contribute. Latest genuine
identity is rechecked before returning a provisional rating. Verified counts, verified
score, signed verified exports and protected-review eligibility exclude these rows.

## API examples

All paths below are relative to `/api/v1`. Worker/reviewer endpoints authenticate
with existing **`guarantor_session` cookie**, not JWT. Browser requests include
credentials and the configured Origin on mutations; production checks exact
`CORS_ORIGINS`. Platform policy endpoints use a dedicated `X-API-Key` with `scoring`
scope and its own organization/environment; no legacy shared-key authorization.
The generated [OpenAPI](openapi.json) describes models, multipart inputs and security.
Do not paste real cookies/API keys in docs or logs.

```sh
# Example development variables, cookies from your existing test login flow:
API=http://localhost:8000/api/v1
WORKER_COOKIE=worker.cookies
OPS_COOKIE=ops.cookies
OPERATION_ID=replace-with-a-new-uuid

curl -b "$WORKER_COOKIE" "$API/me/history-imports/template" -o jobs.csv
# Edit jobs.csv, keeping the authenticated worker_id.
curl -b "$WORKER_COOKIE" -H "Idempotency-Key: $OPERATION_ID" \
  -F 'source_name=Prior customer invoices' -F 'csv_file=@jobs.csv' \
  "$API/me/history-imports"
# Save the returned id and version; preview canonical rows.
BATCH_ID=returned-batch-uuid
curl -b "$WORKER_COOKIE" -X PUT -F 'document=@supporting.pdf' \
  "$API/me/history-imports/$BATCH_ID/document"
# Use the returned version after the attachment (normally 2).
curl -b "$WORKER_COOKIE" -H 'Content-Type: application/json' \
  -d '{"version":2}' "$API/me/history-imports/$BATCH_ID/submit"
# Lost response? Reconcile before retry; never create a new operation blindly:
curl -b "$WORKER_COOKIE" "$API/me/history-imports/operations/$OPERATION_ID"
curl -b "$WORKER_COOKIE" "$API/me/history-imports/$BATCH_ID"
curl -b "$WORKER_COOKIE" "$API/me/history-imports?page=1&size=20"

curl -b "$OPS_COOKIE" "$API/review/imports?page=1&size=20"
curl -b "$OPS_COOKIE" "$API/review/imports/$BATCH_ID"
curl -b "$OPS_COOKIE" "$API/review/imports/$BATCH_ID/document" -o private-evidence.pdf
curl -b "$OPS_COOKIE" -H 'Content-Type: application/json' \
  -d '{"version":3,"decision":"approve","reason":"Ownership compared against verified identity and source references.","ownership_basis":"Document name, account/contact and job references associated with this verified worker."}' \
  "$API/review/imports/$BATCH_ID/decision"
# Worker withdraw: current returned version; rating refreshes on next record read.
curl -b "$WORKER_COOKIE" -H 'Content-Type: application/json' \
  -d '{"version":4}' "$API/me/history-imports/$BATCH_ID/withdraw"

curl -b "$WORKER_COOKIE" "$API/me/additional-verification"
curl -b "$WORKER_COOKIE" -H 'Content-Type: application/json' \
  -d '{"platform_type":"generic"}' "$API/me/additional-verification/cases"
curl -b "$OPS_COOKIE" "$API/review/onboarding/first_party?page=1&size=20"
CASE_ID=returned-case-uuid
curl -b "$OPS_COOKIE" -H 'Content-Type: application/json' \
  -d '{"version":1,"decision":"approve_limited","reason":"Genuine identity and liveness reviewed; limited pilot approval."}' \
  "$API/review/onboarding-cases/$CASE_ID/decision"
```

Responses retain the existing scorer values and add, for example:

```json
{"action":"limited","requirements":[],"reason_codes":["REVIEW_APPROVED"],
 "case_id":"case-uuid","case_version":2,"policy_version":1,
 "evidence_revision":"sha256-digest","review_message":"Limited pilot approved.",
 "restrictions":{"max_active_jobs":1,"max_job_value":"25000","currency":"NGN"},
 "expires_at":"2026-11-15T12:00:00Z","next_steps":[]}
```

Tenant opt-in (use the returned version, default 1 when absent):

```sh
curl -X PUT "$API/platform/onboarding-policy/generic" \
  -H "X-API-Key: $TENANT_SCORING_KEY" -H 'Content-Type: application/json' \
  -d '{"version":1,"settings":{"enabled":true,"allow_limited":true,"allow_approved":true,"approval_days":30,"restrictions":{"max_active_jobs":1,"max_job_value":"25000","currency":"NGN"}}}'
```

`GET/PUT /review/policies/{organization_id}/{platform_type}` offers the same versioned
policy to tenant session reviewers (`?environment=production|sandbox`). Platform types
are `generic`, `domestic`, `ride_hailing`; cases/decisions are separated by type.
Worker case submission accepts `organization_id`, `platform_type`, optional `response`;
requested-information resubmissions require a 10–2,000 character response. The prior
response is immutable while pending and retained in its audit record. Trust queries
still require existing worker consent/mapping and a valid trust-scoped key. Review
approval applies only to that worker/tenant/environment/type/evidence/policy snapshot.

Lists use `page=1&size=20`, size capped at 100; `{items,total,page,size,pages}`. List
imports omit row details; fetch one batch for preview. Requests are limited to
30 mutations/minute/identity and 120/minute/IP in Redis, plus 10 import preparations
per worker per rolling day. Existing protected-review limits remain unchanged.

| Failure | Example code / action |
|---|---|
| No valid session / wrong reviewer | 401 AUTH_REQUIRED / 403 REVIEW_FORBIDDEN |
| Mixed or wrong worker rows | 422 WORKER_MISMATCH; correct source evidence, no import contribution |
| JSON sent to unsigned endpoint | 422 SIGNED_ROUTE_REQUIRED; use signed validator, no downgrade |
| Malformed CSV / unsupported document | 422 CSV_INVALID / DOCUMENT_TYPE |
| Changed payload reuses operation | 409 IDEMPOTENCY_CONFLICT; do not silently create a replacement |
| Existing submitted identical batch | 409 DUPLICATE_IMPORT; use returned existing batch reference |
| Conflicting approved source row | 409 SOURCE_RECORD_CONFLICT; explicit corrected revision required |
| Sandbox identity or missing ownership basis | 409 OWNERSHIP_UNRESOLVED; no provisional contribution |
| Stale review / evidence / policy | 409 STALE_REVISION / STALE_EVIDENCE / STALE_POLICY; reload and review current snapshot |
| Self-review / revoked consent | 403 SELF_REVIEW / CONSENT_REQUIRED |
| First-party unrestricted approval | 409 LIMITED_ONLY |
| Missing genuine checks / scoring rejection | 409 VERIFICATION_REQUIRED / SCORING_RESTRICTION |
| Job count/value / expired access | 409 ACTIVE_JOB_LIMIT / 403 JOB_VALUE_LIMIT / ONBOARDING_REQUIRED |
| Expired attachment | 410 DOCUMENT_EXPIRED; no file access |
| Rate limit / storage or Redis outage | 429 SUBMISSION_LIMIT / 503 EVIDENCE_STORAGE or LIMITER_UNAVAILABLE |

All business failures use `{detail,code}`; limits include `Retry-After`. For an uncertain
prepare, read the operation receipt; for attachment/submission read batch state/version;
for case creation read `/me/additional-verification` in the same policy context; for a
review decision reload the queue/version. Do not retry decisions blindly. Inputs and
IDs are held in memory only, not sensitive persistent device caches. Reloading the
browser discards unsent files; committed drafts remain available through API status.

## Local acceptance commands and release gates

Run against **disposable local databases**, never shared Neon:

```sh
cd backend
DATABASE_URL=postgresql+asyncpg://trust:trust@127.0.0.1:5433/trust_test \
  .venv/bin/python -m pytest -q
TEST_DATABASE_URL=postgresql+asyncpg://trust:trust@127.0.0.1:5433/trust_test \
  .venv/bin/python scripts/check_migration_paths.py
# Test fixtures drop/recreate TEST_DATABASE_URL schema: disposable DB only.
TEST_DATABASE_URL=postgresql+asyncpg://trust:trust@127.0.0.1:5433/trust_test \
TEST_REDIS_URL=redis://127.0.0.1:6379/0 \
  .venv/bin/python -m pytest tests/services/test_admission.py tests/api/test_admission_api.py tests/api/test_admission_limits.py -q
.venv/bin/python scripts/export_openapi.py
cd ../frontend
pnpm typecheck
pnpm lint
pnpm build
```

Browser contract fixtures (separate from live-provider end-to-end testing): start
`NEXT_PUBLIC_API_BASE_URL=/api/v1 pnpm dev --port 3199`, then from repo root:

```sh
npm install --prefix /tmp/trust-browser --no-package-lock playwright
NODE_PATH=/tmp/trust-browser/node_modules \
CHROME_PATH='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' \
  node frontend/tests/admission-browser.mjs
```

Use `BROWSER_BASE_URL` for a different local port, `BROWSER_SCREENSHOT` for an optional
screenshot. Chrome can be replaced with Playwright's installed Chromium. Fixtures
exercise language/file/consent preservation, lost-response receipt recovery, preview,
submission and explicit-role operations UI at 360px. They do not establish real identity
provider delivery, production S3 permissions, Figma parity or low-end device support.
See [iteration evidence and handoffs](iterations/17_admission_and_ownership_imports.md).
