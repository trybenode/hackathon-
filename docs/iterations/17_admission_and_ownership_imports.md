# Additional verification and ownership-reviewed history

Approved plan: verification then review; operations handles ownership, tenant
reviewers decide onboarding. CSV plus PDF/JPEG/PNG required. Genuine identity
and liveness for onboarding; genuine identity for ownership approval. Separate
provisional score capped 0.65, no verified outcome promotion. First-party limited
access: one active job, NGN25,000, thirty days. Preserve signing/auth/normalization.

Stages: models/contracts/roles and migration; immutable unsigned import workflow;
tenant decision engine and review queues; backend job gates; translations, docs
and acceptance. Feature flags default off, API additions nullable for compatibility.
Version review decisions, reject self-review and cross-tenant access, tie approvals
to policy/evidence snapshots. Keep existing funded jobs completable on expiry.

Files stay private with attachment-only reviewer downloads, size/type validation
and thirty-day retention. Local files only in development; production requires
private S3. No raw uploads in public summaries or signed exports.

Verify ownership/worker binding, failed signed no-downgrade, duplicate/idempotent
imports, provisional score isolation, reviewer permissions, stale/concurrent
decisions, limits and expiry, migrations, UI retries and language switching.
Current branch lacks the prior localization modules: new screens receive scoped
typed dictionaries without changing existing auth pages. Figma and real device
signoff remain external gates.


## Detailed stage contracts and implementation record

### 1. Models, contracts, roles and migration

Story: existing integrations keep the same trust decision; an opting-in platform and
its authorized reviewers get a separate onboarding action. Acceptance: nullable additions,
separate roles and tenant/environment/type boundaries, one additive migration head.

Impact: new admission models/schemas/services/router; existing trust query and both private
worker record projections receive additive fields. Shared errors/clock/audit helpers moved
to `feature_common` and reexported from portability to avoid circular dependencies.
No normalization or scorer weights changed. An API usage middleware regression with
prefix-free lazy-router templates was fixed while keeping worker identifiers out of logs.

Data/authorization: six new tables; reviewer memberships, immutable decision records,
versioned policies/cases, import receipts and separate provisional rows. Existing cookie
sessions and hashed tenant keys are reused; operator CLI assigns roles with an audit reason.
Provider references appear only in authorized operations detail, not tenant summaries.

Sequence: model/schema → static Alembic revision → role/consent helpers → additive response
integration. Check migrations from empty, old heads and immediate baseline; verify schema
matches metadata. Rollout: both flags default off; coordinate shared migration deployment.
Rollback by disabling flags; preserve collected audit/evidence tables.

### 2. Unsigned import and ownership review

Story: a worker previews CSV facts, uploads a supporting file, consents and receives an
ownership review; a signed-credential validation failure never becomes unsigned evidence.
Acceptance: one worker, explicit dates/status/cancellation attribution, immutable preview,
private attachment, ownership reason, provisional-only effect at most 0.65.

Impact: existing signed dialog keeps its handler and links to the unsigned workflow.
Separate worker verification hub, import client, ownership service and storage adapter.
Preparation uses an operation UUID + payload fingerprint, worker row lock and unique receipt.
Attachment retries reuse its content hash; submitted evidence requires a new revision to edit.
Decision versions serialize concurrent reviewers. Replacement/withdrawal immediately removes
old eligibility; no new verified outcomes are written.

Sequence: CSV/template/binding validation → receipt/preview → separately bounded attachment →
submit/withdraw/replacement → operations queue → provisional calculation. Requests for more
information remain pending and do not extend initial retention; final review starts its
30-day raw-attachment deadline. Scheduled cleanup handles expiry and uncommitted orphan files;
it is kept out of request handling. Private derived provenance/audits are retained separately.

Dependencies: private S3 and least-privilege credentials for production; external scheduler,
existing genuine identity provider and an operations reviewer. Local files and fake provider
results exist only in isolated tests/development; genuine checks cannot be fabricated by
reviewer UI or the role command. Check malformed, mixed-worker, ambiguous, duplicate,
changed-operation, replacement, unknown-signal, retention and private-download paths.

### 3. Verification, onboarding cases and queues

Story: Building History workers complete real identity/liveness and request review for our
platform or a named consenting platform. Reviewers request information, approve within policy,
decline or revoke. Acceptance: hard-fail cannot be overridden, no self-review/cross-tenant
access, no ownership decision silently approving onboarding.

Impact: policy/evidence-fingerprint evaluator; case submission, consented review queue and
versioned decisions. Worker clarification replies are immutable while pending and audited
with each submission revision. Private record and trust-query assessment fields stay intact.
A canonical context-free assessment fingerprints the evidence so a caller's job context
does not accidentally invalidate an otherwise unchanged approval.

Sequence: current checks → existing scorer/policy → evidence revision → case → reviewer
summary/decision → worker in-app status/reason. Queues use sessions and explicit roles;
external policies can also be configured by a tenant scoring-scoped key. Supported policy
types are generic/domestic/ride_hailing. Named-platform access requires a current history
read grant and WorkerLink at read/decision time, including environment isolation.

Dependencies: Software provides working genuine identity/liveness and worker consent/mapping;
operations/tenant teams supply reviewers. ML reviews unchanged assessment vs provisional
separation. Validate stale evidence/policy, self-review, role/consent revocation, sandbox
checks, requested information, tenant approval and unchanged boolean/assessment.

### 4. Transactional limited access

Story: an approved first-party Building History worker starts one job of at most NGN25,000
within 30 days, with the existing guarantor/payment requirements still in force.
Acceptance: concurrent job creation cannot exceed the limit; expiry/revocation blocks new
work while funded work can complete, dispute and settle.

Impact: shared `enforce_job` runs at job-link creation and unfunded/pending escrow initiation;
worker row locks cover the active count plus write. Existing completion/settlement paths
remain available. There is no price-update path on this branch; future updates must call
the gate and keep currency/amount rules consistent. External restrictions are advisory
contracts for the integrating platform to enforce in its own transactional system.

Sequence: assess permission/expiry → amount check → active count under worker lock → existing
job and protection logic → commit. Validate true PostgreSQL concurrent decisions and creates,
value boundary, expiry/revocation and completion/release of already funded jobs. Providers
are stubbed only in tests; this establishes enforcement behavior, not live financial cover.

### 5. UI, documentation and acceptance

Story: workers understand review and restrictions in four languages, retain input during
switches/network failures, and developers can reproduce the API workflows.
Impact: scoped worker language provider with non-sensitive preference cookie and typed
candidate dictionaries. This branch did not have the earlier localization implementation;
only new review/import worker states are localized. Existing authentication/guarantor pages
and other workflows are preserved. Fallback error/provider/user content remains original.

Sequence: functional screens → API examples/security/retention docs → live-schema OpenAPI
export → backend/PostgreSQL/Redis checks → frontend types/lint/build → 360px browser fixtures.
The browser fixture checks a failed prepare response with receipt reconciliation and no
second POST; it also checks operations decision UI. All uploads/accounts are isolated fixtures.

Rollout: feature flags stay off until provider/storage/scheduler/operator setup is verified.
Expose no claim of reviewed translations, real financial protection or low-cost device
support without separate acceptance evidence.

## Integration checklist and handoffs

| Owner | Dependency/contract | Acceptance evidence | Remaining signoff |
|---|---|---|---|
| Feature implementer | Additive record/trust action, versioned review/import APIs | Automated results below; generated OpenAPI and API examples | Code review of this branch |
| Software Engineer | Genuine identity/liveness, private S3, Redis, role bootstrap, scheduler, migration deployment | Private reference available to operations, stubs rejected, local schema/Redis checks | Real provider/storage/scheduler smoke test and shared deployment coordination |
| Operations | Ownership association, independent source/contact cross-check and documented basis | Explicit role/self-review/version rules; private attachment UI | Pilot reviewer training and operational review standards |
| Platform owner | Explicit opt-in policy, tenant reviewer roles, current consent/mapping, enforce own restrictions | Tenant approval/isolation/policy invalidation regressions | Adopt onboarding action without changing legacy decision semantics |
| ML Engineer | Existing verified scorer and separate provisional rating | No NormalizedOutcome promotion; unknown rows unscored; capped provisional; assessment unchanged after tenant approval | Review signal eligibility and before/after assessment examples |
| UI/UX + native reviewers | Import preview, ownership discrepancies, requirements, pending/reviewer states, restrictions | Functional 360px browser checks; candidate-language warning | Figma references/comparison, native-language review, real low-cost Android test |
| Docs/Presentation | Supported versus planned capabilities | Reproducible setup, examples, failures, boundaries and release gates | Review claims against actual provider/device pilot evidence |

## Acceptance evidence

Validation uses local Docker PostgreSQL/Redis and isolated browser fixtures. No shared
Neon schema, provider account or production job was changed. Authentication account/session
creation and normalization/scoring weights were not modified.

Final verification on this working tree (2026-10-16):

- Full backend suite, SQLite fixtures + isolated Redis: **331 passed, 2 skipped**.
  The two skipped checks require PostgreSQL (one pre-existing review concurrency
  check and the new onboarding/job concurrency check); the new one ran in the
  PostgreSQL acceptance suite below. The existing one was not included in that
  targeted suite, so no claim is made that every legacy test ran on PostgreSQL.
- New ownership/onboarding API/service checks + existing escrow service suite on
  local PostgreSQL/Redis: **44 passed**, including simultaneous reviewer decisions,
  simultaneous job creation, tenant policy invalidation, and funded completion/release
  after access expiry or revocation.
- Migration paths **empty / 1d7fe6fb9d97 / 8f41c20a9e37 / c5b96592228a → head** all pass;
  each migrated schema matches ORM metadata. Final head: **a7d01e264c90**.
- Frontend **typecheck, full lint and production build pass**.
- Local Chrome browser fixtures pass at **360×800**: English/Yoruba/Hausa/Igbo
  language switching preserves form values/files/consent; a lost prepare response
  reconciles through the receipt without a second POST; preview/submission and the
  explicitly authorized operations review UI work without runtime exceptions or
  horizontal overflow. Screenshot inspected for functional layout only.
- OpenAPI regenerated from the combined app: **90 paths**, existing cookie-session
  and platform-key security descriptions retained.

Outstanding release gates: real identity/liveness delivery (existing stub is not
eligible), production private S3 permissions and retention scheduling/monitoring,
operator/reviewer assignment and training, platform adoption/enforcement, Software/ML
review, Figma comparison, native-language comprehension review and a representative
low-cost Android/network pilot. No production readiness claim follows from mocked
browser/provider fixtures or local Docker checks. Both rollout flags remain false
in defaults/examples; no deployment, push or shared database migration was performed.
