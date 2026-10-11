# Iteration 14: one Vercel project with services

Purpose: replace the two-project deployment with independently built backend and
frontend services; preserve the existing browser API, cookies and workflows.

1. Acceptance: frontend serves all public paths, including /api/v1 via its existing
   proxy; backend is internal. Names and visibility require operator confirmation.
2. Impact: root deployment configuration, runtime destination resolver, public SSR,
   deployment examples and guide. No auth, scoring, schema or migration changes.
3. Design: frontend binds backend as BACKEND_URL. Runtime functions resolve the
   binding first; container/local origins remain fallbacks. Existing secret headers,
   authorization, receipts and response handling remain unchanged.
4. Dependencies: Vercel Services beta, Python 3.12, Node 24/pnpm, Neon, Redis and
   existing provider settings. Bindings are injected, never manually configured.
5. Sequence: write service config; update resolver and SSR; document deployment;
   run frontend checks and proxy smoke; show final config for confirmation.
6. Verification: binding precedence and invalid destination behavior, frontend
   typecheck/lint, proxy preservation, cloud vercel dev/build still separate gates.
7. Rollout: root directory is repository root. Existing per-directory configs remain
   standalone fallback profiles. No deployment performed. Rollback uses the prior
   two-project profile. AI/speech/workers and automatic maintenance remain disabled.

## Validation evidence

- Frontend typecheck and lint passed.
- Production webpack build passed. Default Turbopack build could not finish in
  this execution environment: font network restriction, then helper-port denial.
  The configured pnpm build remains unchanged; its Vercel build is still pending.
- Built proxy smoke passed with BACKEND_URL pointed to the fake local upstream
  and API_PROXY_ORIGIN deliberately unusable, demonstrating binding precedence.
  Cookies, receipts/idempotency headers, origin, authenticated IP, response status,
  audio, upload limits, unavailable upstream and token-safe logs passed.
- Structural config/binding checks and scoped whitespace checks passed.
- Vercel CLI is not installed here; vercel dev and cloud acceptance not performed.
- Service names/public routing/binding await user confirmation. No deployment,
  database changes or Git push performed; pre-existing AGENT.md changes preserved.
