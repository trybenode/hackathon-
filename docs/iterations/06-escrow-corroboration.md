# Iteration 6 — conditional escrow corroboration and hardening

## Current evidence and dependency
The repository has escrow/provider-operation records but no authenticated payer mapping or live payment integration. Successful protection records alone do not identify the payer or prove that the payer hired the worker. This iteration therefore installs an explicit unavailable boundary and regression tests; it does not invent provider payloads, process payments, or retroactively protect historical claims.

## Detailed future integration gate
Software must supply a documented authenticated provider contract, verified callbacks/status retrieval, idempotency behavior and job/customer/payer mapping (including third-party payers). Only then implement an adapter returning independently validated references and timestamps. Recheck funded/released/refunded/failed/reversed state, replay/forged callbacks and account mapping before granting a corroboration label. Preserve dual completion, dispute exclusions and protected-review eligibility. ML reviews any future eligibility impact separately; this slice changes no scores.

## Acceptance and rollout
The default boundary returns not_available even if escrow rows are marked successful. No payment or KYC sandbox becomes genuine corroboration. Test this against existing escrow fixtures. Deployment is disabled until real integration evidence and Software security/migration signoff exist. Prototype configuration is not proof of payment, identity, language comprehension or device support. Figma, actual SMS delivery, model hosting/recording evaluation and representative Android testing remain separate release gates.
