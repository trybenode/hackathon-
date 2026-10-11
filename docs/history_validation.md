# History/language pilot validation — 2026-10-09

Baseline: `f0bb9ee` (PR #18 already merged). Implementation is in the working tree; no deployment, migration of shared environments or team approval was performed. Existing account authentication, `normalisation.py`, scoring rules and protected-review requirements are preserved. README notes already present were retained; only a setup-reference section was appended.

## Local evidence

| Check | Result | Practical limit |
| --- | --- | --- |
| Full backend suite | **189 passed, 4 skipped** | In-memory SQLite; does not establish PostgreSQL locking or provider delivery |
| New regression coverage | 22 passing tests across history services, HTTP boundaries, processing, provider/limits | Fixtures/mock inference/SMS do not establish actual speech/translation quality |
| Frontend type checking | Passed | Static checking, not interaction/comprehension evidence |
| Frontend ESLint | Passed, no warnings | Does not replace browser/accessibility testing |
| Frontend production build | Passed using `pnpm exec next build --webpack` | Default Turbopack failed on environment port binding; an initial build also failed fetching existing Google Fonts |
| Alembic heads | One head: `a83c2d43e9f2` | Graph check only |
| PostgreSQL offline SQL | Complete empty-to-head migration SQL generated successfully | No live upgrade, downgrade or metadata-drift result |
| OpenAPI snapshot | Regenerated from actual app: 64 paths | Includes actual cookie authorization and typed new responses |
| Public summary privacy/size | Integrated test verifies aggregate counts, no contact/claim/conversation/token leakage; below 20 KB | Test fixtures, not a production load benchmark |
| Normalization/scoring/auth changes | None in this slice | External shared-contract review remains required |

Regressions cover: private details denied to bearer-only links; scoped cookies cannot authorize other requests; wrong/expired/replayed codes and committed attempt counters; five deliveries/request and provider-reference binding; persisted development sandbox access rejected in production; account-to-job matching and changed customer mappings; revision invalidation/archive/revocation; duplicate writes and operation receipts; response withdrawal; explicit declaration retained; no relationship-declared label before declaration or for an unrecognized job; original message preservation and cross-request isolation; numeric translation rejection; missing provider/error recovery; queued drafts requiring approval; idempotent approvals; transient cleanup; exhausted/stale lease fencing; separate counts in canonical/public records; exclusion from verified credential exports and unchanged assessments.

The four skipped checks require isolated services: existing review PostgreSQL concurrency and Redis checks, plus the new history PostgreSQL concurrency and Redis checks. They are wired to `TEST_DATABASE_URL` / `TEST_REDIS_URL` and the existing CI service configuration. PostgreSQL/Redis binaries were absent and the local Docker daemon was unavailable. No shared or Neon database was used for these checks.

Browser setup found no connected browser. No browser/Figma comparison, 360 px interaction pass, microphone exercise, physical Android performance measurement or real-user pilot was claimed. ffmpeg/ffprobe and the optional heavyweight model environment were unavailable locally; inference tests substitute explicit test fixtures. No real SMS or actual model inference was sent/run.

`git diff --check` flags a trailing space in a README note already present before this work; that note was preserved. No other tracked whitespace issue was reported. New files remain available for review without a commit or push.

## Iteration status and release gates

| Iteration | Local implementation | Release dependency |
| --- | --- | --- |
| 1 Attribution | Text entry, preview/invite, hashed capabilities, Twilio adapter/dev challenge, scoped recipient cookie, matching account, explicit receipts, revoke/withdraw/edit | Real SMS/Nigerian-number delivery and provider fraud controls; actual customer session demo; security/log review |
| 2 Page translation | Source-controlled candidate en/yo/ha/ig dictionaries, server preference, pilot/fallback notices, core actions/consent/errors | Native-language review; glyphs/long-text/meaning comprehension; untranslated existing/dynamic content remains English |
| 3 Voice history | Recording/upload UI, durable leased queue, private spool, official-model adapter/gateway, editable draft/approval and retry | ffmpeg/ffprobe, gateway access/compute, actual recordings/evaluation, spoken instruction assets and retention monitoring |
| 4 Clarification | Private async original messages, separately stored machine translations/model revision, send receipts, no runtime live chat | Actual pair/negation/date/amount validation, browser authorization/network exercise |
| 5 Record/share/pilot | Canonical/compatibility/public aggregate integration and documented reproducible HTTP paths | Live PostgreSQL/Redis, Figma, 360 px browser, physical low-cost Android and actual user pilot |
| 6 Escrow | Explicit unavailable evidence boundary, no fabricated provider mapping | Authenticated payment contract/callbacks, third-party payer handling, refunds/reversals and authoritative hiring-customer mapping |

Use [integration handoff](integration_handoff.md) for named owners and required Figma frames. No strong payment, genuine contact, native-language, independent verification or device-support claim should exceed its own acceptance evidence.

## PostgreSQL migration follow-up — 2026-10-10

A live Docker PostgreSQL 16 run exposed duplicate generated unique-constraint names
on `history_claims`: both worker/operation and worker/job used
`uq_history_claims_worker_id`. The model and still-unpublished attribution migration
now explicitly use `uq_history_claims_worker_operation` and
`uq_history_claims_worker_job`.

Re-ran `scripts/check_migration_paths.py` against the disposable Docker server on
localhost:5433. All three paths passed (empty, `1d7fe6fb9d97`, `8f41c20a9e37` →
`a83c2d43e9f2`), and each migrated schema matched the models. Only temporary
`integration_*` databases were created/removed; no shared database was changed.
The remaining PostgreSQL runtime/concurrency and Redis gates are separate checks.

## Worker page language and private speech — 2026-10-10

Implementation: shared language selection across worker screens and dialogs,
scoped worker sign-in copy, original/translated clarification messages,
on-demand authenticated speech status/content, private 24-hour storage,
durable processing leases, translation fingerprints and deduplication.
Protected review, scoring and authentication logic were not extended.

Validation evidence:

- Full backend suite: **242 passed, 5 skipped**. PostgreSQL-only concurrency is
  skipped in the default SQLite suite; the existing external-service skips remain.
- Isolated local PostgreSQL/Redis run: **21 passed**, including concurrent speech
  task creation, scoped playback, revoked requests and limiter integration.
  The later speech-gateway response contract test passed in the full SQLite run.
- Five disposable PostgreSQL migration paths (empty, stored-score head,
  portable-history head, history head and escrow merge head) passed and matched
  ORM metadata. One Alembic head: `a85c2d43e9f4`.
- Applied additive migrations to local Docker `trust_dev`; no shared/Neon
  database was migrated.
- Frontend `pnpm test:language`, `pnpm typecheck`, and `pnpm lint` passed.
  The language check covers candidate core copy, English fallback, formatting
  and prevention of translated enum/identity attributes.
- No browser connection was available. Interactive language-switch recovery,
  360 px layout, Figma, physical Android testing and native-language review remain
  unverified. Real N-ATLAS translation quality and speech pronunciation/delivery
  require configured providers and reviewers; speech stays disabled by default.

Changes made because: workers need consistent navigation and consent meaning
in their selected language; translated messages need a separate private audio
path with current authorization instead of exposing files or claiming N-ATLAS
itself supplies speech synthesis.

## Spitch adapter follow-up — 2026-10-10

Added direct Spitch speech selection, explicit per-language voice configuration,
MP3 validation and bounded responses. Audio fingerprints now include provider,
model/configuration revision and voice to prevent stale playback after changes.
No schema or public API changes; existing authorization/retention paths reused.

Full backend run: 256 passed, 5 skipped. Subsequently added a persisted
voice-change queue regression; targeted speech/Spitch/history API run:
30 passed, 1 skipped (PostgreSQL-only concurrency test). Tests mock the external
HTTP service; no API key, paid call or real pronunciation validation was used.
No frontend changes in this follow-up. Real Spitch and N-ATLAS access, native
review, browser/mobile/device gates remain open. Speech remains disabled by
default. Setup and candidate voices are documented in history_and_language.md.

## Production deployment preparation — 2026-10-11

Added managed-container configuration for Railway/Render, production settings
validation, development-provider guards, dependency readiness, supervised history
processing, coordinated migrations and the same-origin frontend API proxy.
Existing authentication, normalization and scoring rules were preserved.
Security updates pin Next/eslint-config-next 16.3.8, sharp 0.35.5,
source-map-js 1.2.2, FastAPI 0.143.0 and Starlette 1.3.1.

Validation on the current working tree (no release commit was created):

- SQLite backend: **277 passed, 5 skipped**.
- Disposable local PostgreSQL and Redis: **282 passed**, no skipped tests.
- All five migration paths passed and matched ORM metadata, with one head
  `a85c2d43e9f4`. These checks created/deleted only temporary databases.
- Frontend type checking, lint and language checks passed; standalone production
  build passed using webpack. The proxy smoke verified cookie forwarding,
  idempotency, origin/IP handling, private audio responses, upload limits,
  upstream failure and token-safe logs.
- Both runtime dependency audits reported **no known vulnerabilities**.
- Production supervisor smoke passed readiness, online preflight and coordinated
  shutdown after worker failure. Backend Docker image passed actual API/worker
  readiness, migration execution and preflight while running as UID 10001.
- Both final Docker images built successfully; the frontend container used its
  normal Turbopack build. Running both images together passed frontend/backend
  readiness, same-origin API forwarding, unauthenticated worker rejection and
  public-link privacy headers. Native sharp 0.35.5 image generation passed.
  Python 3.12 container OpenAPI exactly matched the exported snapshot.
- Render/Railway configuration files were validated against provider JSON schemas.

No cloud resources, public deployment or production database were modified.
Real email/SMS/identity/payment/AI/speech providers, managed-ingress IP mapping,
backup restoration, native-language review, staging browser flows, Figma/360 px
and physical Android testing remain separate launch gates. See
[production deployment](production_deployment.md) for deployment and rollback.
