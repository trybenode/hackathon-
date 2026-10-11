# Iteration 1 — customer attribution and text confirmation

## Stories and acceptance
Workers create informal claims or annotate their own completed/released system jobs. An informal recipient must verify the exact intended phone before reading private details or responding. A system recipient must have an existing session matching the authoritative hiring customer. Forwarded tokens alone never authorize access. Contact verification establishes contact control, not a historical hiring relationship. Neither response type changes scoring, outcomes, protection, or review eligibility.

## Repository impact and design
Add dedicated claim, request, response persistence, schemas, a service, and thin versioned routes. Claims never enter normalized outcomes. Existing session authentication and normalization remain unchanged. Use the existing feature error/audit helpers. Append a migration after the actual current Alembic head. Worker inputs are revisioned, request snapshots immutable, and secrets hashed.

Owner writes require an idempotency UUID and a worker row lock. Requests expire in seven days. SMS challenges expire after ten minutes, allow five checks, five deliveries per request and a sixty-second resend interval; scoped recipient sessions expire after thirty minutes and are invalidated on revoke/edit/archive. System account matching remains live on every access. A single final response is persisted per request; retries return the receipt, changed payloads conflict. Recipient withdrawal removes active confirmation while retaining audit. Editing revokes prior requests and invalidates prior-revision evidence. Paginate lists at 20, maximum 100.

## Dependencies and execution
Use Twilio Verify as the first replaceable SMS provider adapter; keys/service SID and Nigerian-number delivery validation are Software dependencies. Without configuration, only development may use a non-logging code stub, clearly sandboxed. Production fails closed. No registration or email-login extension. Customer browser sessions remain a Software dependency. UI/Figma and native-language review are external gates.

Implement models/migration and typed provider/service first; then routes, business/security tests, text-first worker and recipient screens, and documented API examples. Reconcile lost request secrets via an operation receipt and revoke before replacement. Enforce Redis limits and same-origin checks on browser mutations. No real SMS is sent during tests.

## Verification and rollout
Cover wrong customer, missing attribution, wrong/expired/replayed code, wrong guest session, revoke/edit/archive, idempotency conflicts, response concurrency, withdrawal, pagination, and assessment isolation. Run backend suite and migration checks, frontend type/lint checks, and browser checks where available. Feature configuration may disable these routes. No genuine SMS/KYC/escrow or visual/device support claim until external gates pass. Rollback disables the feature before a coordinated migration downgrade; no existing records are rewritten.
