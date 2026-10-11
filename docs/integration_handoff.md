# Weekly integration: owners, dependencies and acceptance

Baseline: main `a3412d0`; integration changes are in the working tree.
This document records assignments, not completed external team approvals.
Authentication and the teammate's `normalisation.py` were preserved.

| Priority / item           | Implemented contract or behavior                                         | Owner / reviewer                                       | Acceptance or dependency                                                                                      |
| ------------------------- | ------------------------------------------------------------------------ | ------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------- |
| P0 record contract        | `/me/record` canonical; compatibility projection; paginated history    | Feature implementer; Software review                   | Contract/evidence agreement covered by API tests; external review pending                                     |
| P0 migration coordination | Merge both original heads; add operation receipt migration               | Feature implementer; Software deploys                  | Empty/both-head PostgreSQL checks; coordinate shared migration before deployment                              |
| P0/P1 scoring semantics   | Conservative adapter, missing ratings, source namespaces; fingerprint v3 | Feature implementer; ML review                         | Scoring regressions pass; review legacy reassessment behavior before merge                                    |
| P1 truthful presentation  | Latest identity, sandbox, guarantor lifecycle, attributable completion   | Feature implementer; Software + ML review              | Regression coverage; production evidence writers remain Software dependency                                   |
| P1 credentials            | Signed export; JSON/token import; duplicate feedback; refresh            | Feature implementer; UX review                         | API integrity tests; browser interruption and Figma review pending                                            |
| P1 sharing                | Standard preview; seven-day links; revoke; receipt reconciliation        | Feature implementer; UX + Software review              | Public privacy/live evidence tests; browser clipboard/WhatsApp and upstream logging review pending            |
| P1 platform access        | Named approval, permission/tenant checks, historical exchange            | Feature implementer; Software approves platforms       | Two-platform tests; operator-reviewed attestation issuance needed for real use                                |
| P1 reviews                | Owned customer list → eligibility/form → private receipt               | Feature implementer; Software supplies access/evidence | Review restriction/concurrency tests; genuine customer session and authoritative jobs needed for browser demo |
| P2 docs                   | OpenAPI, request examples, two-platform walkthrough, this checklist      | Feature implementer; Docs/Presentation review          | Reproduce examples in isolated environment; distinguish supported and planned claims                          |
| P2 visual/device          | Existing components used for functionality                               | UI/UX supplies Figma; QA tests Android                 | Pending; no physical device-support claim                                                                     |

## Figma reference checklist — UI/UX Designer

Supply a Figma URL plus frame/node IDs or annotated screenshots. Each item needs
360 px mobile and relevant desktop frames, readable long text, accessible focus,
loading/error/empty states and touch targets. Functionality can proceed using
current components; visual signoff is pending these references.

- [ ] Worker profile + portable record: stored score versus confidence, Building History, sandbox identity, lifecycle states.
- [ ] Credentials + import dialog: file/paste, malformed/tampered/expired token, duplicates, imported counts, uncertain retry, export error.
- [ ] Work history: verified/self-declared distinction, provenance, unknown rating, completion labels, pagination.
- [ ] Share preview + links: generate, copy/WhatsApp, active/expired/revoked, uncertain operation, revoke unrecoverable link.
- [ ] Public verification: valid summary, invalid/expired/revoked link, service unavailable; no private fields.
- [ ] Platform approvals: named-platform read/import explanations, one-time token, uncertain approval, expiry/revocation.
- [ ] Customer jobs + review: attributed job entry, eligible/ineligible reasons, duplicate receipt, rating/comment validation, 429/503 and uncertain submission.

## External review and release gates

- [ ] Software Engineer: validate contract compatibility and customer browser access; coordinate both migrations and deployment.
- [ ] Software Engineer: authoritative customer attribution, explicit dual completion, funded escrow, premium/cover and dispute evidence; all eligibility writers coordinate the job row lock.
- [ ] Software Engineer: reviewed platform attestation issuance, trusted-proxy settings and token-redacted upstream logs.
- [ ] ML Engineer: review [fictional before/after cases](scoring_comparison.json), then compare old/new assessments on agreed representative fixtures; approve conservative eligibility, confidence interpretation and separate starting history.
- [ ] UI/UX Designer: attach references above and approve visual comparison.
- [ ] QA: run interactive flows at 360 px, interrupted network, keyboard/focus and representative low-cost Android.
- [ ] Docs/Presentation Lead: reproduce the documented flows and approve supported-versus-planned claims.

No team member was contacted automatically. Real KYC, payment protection,
SMS/USSD, persistent offline queues, prior-customer attestation and independent
issuer key discovery are outside this integration slice.

## Worker language / private speech handoff (2026-10-10)

- Feature implementation: worker page copy and shared preference, scoped worker sign-in presentation, current-thread translation and private speech tasks implemented. Backend migration graph now has one head.
- Software: deploy the additive merge/table migrations, connect an authenticated speech gateway implementing the documented contract, run the history worker with shared private spool storage across API/worker processes. Confirm production HTTPS and retention sweep operation.
- ML/native reviewers: approve English↔Yoruba/Hausa/Igbo translation, negation/date/amount preservation and exact-text pronunciation before adding language codes to HISTORY_SPEECH_LANGUAGES. Page dictionaries are candidate copy, visibly marked pending review.
- UI/UX: compare all worker pages, language-switch form preservation and Translate/Listen states against 360 px/mobile frames. No connected browser was available for this session; browser, Figma and physical-device acceptance remain open.
- Docs/presentation: describe configured text translation and validated speech as separate capabilities. No N-ATLAS TTS, real speech delivery or native-language accuracy claim is supported by adapter tests alone.

## Managed deployment handoff

Production preparation targets Railway/Render. See production_deployment.md and
iteration 11. Software owns provider secret configuration, verified email/domain,
managed Postgres/Redis, direct migration URL, private disk and ingress IP testing.
API/worker must remain one disk-attached instance until file storage is shared.
Identity/liveness and no-key payment stubs are blocked outside development.
SMS, model/speech validation, native copy/pronunciation review and browser/device
checks remain separate release gates. Docs/Presentation must not claim those
providers or a live deployment based on container/configuration checks alone.
