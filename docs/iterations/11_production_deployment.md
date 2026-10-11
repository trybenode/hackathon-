# Production deployment preparation — detailed plan

1. Stories/acceptance: operators build immutable frontend/backend images and deploy to Railway or Render; existing browser sessions work through a same-origin API proxy. Bad production configuration prevents startup. Dependency/worker failures fail readiness without exposing secrets. Real provider absence never produces successful sandbox verification/payment.
2. Repository impact: Dockerfiles, Render blueprint, production launcher, settings validation, health endpoints, narrow frontend proxy and safety guards on existing stub providers. Preserve registration/sign-in, scoring and normalization. Read installed Next.js standalone, self-hosting and route/proxy documentation first.
3. Contracts/data: add liveness/readiness endpoints; no feature migrations. Backend validates required production secrets/HTTPS origins/email. A server-only shared proxy secret authenticates forwarded client IP, with IP parsing and browser origin checks; ignore arbitrary client forwarding headers. Durable history processing runs in a separate child process inside the single backend instance, sharing a private mounted disk. Explicit migration job precedes serving traffic; no migrations inside each web replica.
4. Dependencies: provider account/domain, managed PostgreSQL/Redis, production URL, transactional email, deployment secrets, persistent disk ownership, SMS/payment/identity integrations, native-language review and device/Figma gates. User selected managed containers; do not create cloud resources or deploy publicly in this iteration.
5. Sequence: settings/stub guards and tests; readiness/supervisor; same-origin frontend proxy and standalone containers; Render blueprint/Railway guide; production preflight, regression/build/container checks; documentation and OpenAPI.
6. Verify: invalid secrets/origins, disabled providers, readiness dependencies, proxy credential isolation/spoofed IP, cookie forwarding, supervisor shutdown, full backend tests, frontend language/type/lint/build, image build/start smoke tests when Docker/network are available. Existing PostgreSQL/schema paths remain CI gates.
7. Rollout: use staging first, back up DB and apply additive migrations once, then deploy API/frontend, exercise authenticated flows, monitor readiness and queued work. One backend instance until private file storage becomes shared object storage. Disable optional AI/speech until validated. Roll back application images with forward-compatible schema; never downgrade/delete user data blindly. Provider deployment remains user-operated.

Security audit follow-up: the initial production frontend audit reported nine
advisories, including a critical next/og package advisory. Package advisories do
not establish that this application uses every vulnerable code path; upgrade
within Next 16.3 rather than accepting known-vulnerable deployment dependencies.
Apply Next/eslint-config-next 16.3.8 and patched sharp/source-map-js versions as
needed, then repeat audit/build/proxy smoke checks. Audit backend runtime pins too
and address confirmed fixable findings before treating image validation as final.

Security changes: Next/eslint-config-next are pinned to 16.3.8; workspace
overrides require sharp 0.35.5 and source-map-js 1.2.2. FastAPI 0.143.0 and
Starlette 1.3.1 replace the vulnerable backend framework versions. Both runtime
dependency audits pass. The frontend Dockerfile includes pnpm-workspace.yaml
so the lockfile overrides and explicit build-script policy also apply in CI.
The backend sets the actual runtime user's home directory after dependency
installation so asyncpg does not attempt certificate access under /root.

Completion evidence (2026-10-11): 282 PostgreSQL/Redis tests passed, all five
migration paths matched metadata, both Docker builds and combined-container
readiness/proxy/privacy/image-processing smoke passed. Frontend types, lint,
language checks and standalone builds passed; both runtime audits are clear.
CI also runs production supervisor and API proxy smoke tests. See
../history_validation.md for results and ../production_deployment.md for
configuration, operational limits and the remaining human/provider launch gates.
