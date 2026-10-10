
# Revised plan: inclusive trust and portable work-history infrastructure

## 1. Product position and competitor lessons

The proposed selling proposition is:

**“Make informal work count: portable, verifiable work history that workers can share and platforms can use, built for low-cost devices and unreliable connections.”**

This combines three priorities: credible evidence, inclusion, and integration into existing services. It is a positioning hypothesis to validate, rather than a proven unique capability.

| System              | Publicly described strengths                                                                                                                                                    | What we should adopt or improve                                                                                                                                                                                                                                                                                                 |
| ------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Trustory**  | Portable professional records, institution-backed verification, consent-controlled access, and traceable corrections. It explicitly separates evidence from a reputation score. | Preserve evidence provenance, worker control, and correction history. Add a practical developer integration and measurable weak-network experience.[Source](https://www.trustory.africa/how-it-works)                                                                                                                            |
| **Vetted**    | Nigeria-focused portable badges, WhatsApp sharing, guarantors, and an incident-review process with worker right-of-reply.                                                       | Make sharing simple and verification understandable. Separate identity, work evidence, and protection status; avoid unreviewed accusations becoming authoritative trust signals.[Source](https://vetted.ng/)                                                                                                                     |
| **LaborHack** | Vetted and certified artisans, hiring services, insurance, and guarantees. Its published material explains that direct bookings bypass its protection services.                 | Give users concrete reasons to remain in a protected workflow: payment assurance, recourse, and recorded outcomes. Carry evidence into other participating platforms.[Services](https://www.laborhack.com/subscriptions), [published booking guidance](https://blog.laborhack.com/top-certified-electricians-in-lagos-laborhack/) |

These comparisons cover public descriptions, not authenticated product testing. We have not established that competitors lack APIs or weak-network support.

**The payment analogy:** OPay and Moniepoint describe inclusion through accessible services, agent networks, and support; Moniepoint also describes USSD access. The relevant lesson is distribution and assistance alongside technology. “Payments enabled participation; portable work evidence can enable opportunity” is a useful thesis. Calling trust “the second wave” remains a pitch hypothesis. [OPay](https://static.opayweb.com/about-us), [Moniepoint](https://ng.moniepoint.com/blog/how-weve-built-a-bank-in-every-neighbourhood)

Platform retention and worker portability must coexist. Our API can make recorded jobs more valuable and protected workflows more attractive. It cannot prevent private transactions or establish facts that nobody reports. Cutout reduction must be measured, not promised.

## 2. Weekly implementation

### Authentication boundary

**Do not extend or redesign the existing email-code sign-in.** Do not add worker/customer registration or seeded-account login flows.

Reuse authenticated ownership checks where valid sessions already exist. Working worker/customer access is a dependency for the Software Engineer. API tests may use authentication fixtures; those fixtures do not establish that the browser journey is complete.

### A. Worker credential import/export

- Add an authenticated worker-record endpoint and connect the existing profile/portable-record screens to persisted data.
- Connect export to the existing signed credential endpoint. Refresh its assessment first and download the returned bundle with issuance and expiry information.
- Add JSON-file and pasted-token import, validation errors, duplicate-import handling, imported-count feedback, and refreshed records.
- Show verified work evidence separately from self-declared historical claims.
- Use actual bands, evidence confidence, source labels, and timestamps. Remove mocked score percentages and unsupported punctuality statistics from live flows.
- Preserve current worker-bound credential compatibility. Validate credentials centrally through our service; participating companies do not receive our signing secret.
- Treat exported history as portable evidence. A receiving platform recalculates its own assessment rather than inheriting another platform’s acceptance decision.

### B. Shareable verification page

Replace mandatory scope checkboxes with **Share verification → preview → generate link**.

The standard summary includes:

- Worker-approved display name, role, and general operating area.
- Identity-check status, including sandbox status where applicable.
- Trust band, evidence confidence, explanation, and assessment timestamp.
- Aggregate work-history counts with verified and self-declared evidence distinguished.
- Active guarantor status when supported by stored records.

It excludes individual client identities, contact details, raw documents, identity numbers, provider references, credential tokens, and detailed adverse allegations.

Implement:

- Owner endpoints to create, list, and revoke share links.
- A share-grant table storing a random token hash, owner, creation time, seven-day expiry, and revocation time.
- A public `/verify/{token}` page showing current permitted evidence.
- Copy-link and WhatsApp sharing, expired/revoked states, and immediate server-side revocation.
- Uncached result responses, `noindex`, restrictive referrer handling, and token-redacted logs.

Detailed history is approved separately for a **named integrating platform**. Workers do not need to understand technical scopes; the approval screen explains the information and purpose in plain language.

### C. Restricted reviews

Retain the agreed SRS rules:

- The verified hiring customer may submit one review after explicit customer and worker completion confirmation.
- The job must be independent and have persisted protection evidence and a completed outcome.
- Auto-release alone does not unlock a review.
- Open disputes, unsupported customer attribution, failed/refunded protection, and existing reviews block submission.

Add eligibility and submission endpoints, a customer-facing review screen, and a review table with a unique job constraint. Accept an integer rating of 1–5 and an optional comment up to 2,000 characters.

Enforce the previously selected defaults: five submission attempts per minute per user, thirty per minute per IP, and ten successful reviews per reviewer over a rolling 24 hours. Enforce uniqueness and velocity limits under concurrent requests; return retry information when limited.

Persist the review, linked outcome rating, and audit event atomically. Keep review comments private in this version. Do not convert review text into safety flags or introduce new scoring weights.

Past jobs without protection remain eligible for historical evidence import. They do not become eligible for this protected-job review system.

### D. Essential developer API slice

Support this journey:

**Outside work history → our evidence service → worker approval → receiving platform’s onboarding/history view.**

Add:

| Interface                                                      | Behavior                                                                                             |
| -------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------- |
| Worker platform-grant endpoints                                | Approve, inspect, and revoke a named platform’s history access/import permission; seven-day expiry. |
| `POST /api/v1/platform/worker-links`                         | Bind a platform’s external worker ID to our worker identity using a valid worker-approved grant.    |
| `POST /api/v1/platform/workers/{external_id}/history/import` | Receive historical records with source metadata and an idempotency key.                              |
| `GET /api/v1/platform/workers/{external_id}/history`         | Return approved, paginated history with verification provenance.                                     |
| Existing`/trust/query`                                       | Use the authenticated platform and valid worker grant to authorize the assessment request.           |

Implementation requirements:

- Replace the shared-key assumption for these integrations with a platform principal derived from a hashed, revocable API key and an organization relationship.
- Preserve the old shared key only for existing development/demo compatibility; it cannot authorize the new history interfaces.
- Store platform-worker mappings, grants, and record provenance. Never match workers solely by names, phone numbers, or guessed UUIDs.
- Deduplicate by canonical worker, authoritative source, and source record ID. Repeated identical idempotency keys return the original result; changed payloads using the same key return a conflict.
- Receiving records through an API does **not** make them verified. Self-declared uploads stay unverified.
- A reviewed platform may attest its own records only when its credential has explicit attestation authority. Record who attested, when, and the verification method; caller-supplied `verified: true` is insufficient.
- Return evidence status and missing-data information. Only eligible verified evidence enters full trust scoring; self-declared imports remain in the separate existing starting-history path.
- Provide a small two-platform integration example and updated OpenAPI documentation. Do not build or distribute a full SDK this week.

Detailed history access must recheck grant expiry and revocation on every request. Revocation prevents subsequent access; it cannot recall information a recipient already downloaded.

### E. Low-cost devices and weak connections

Ship lightweight pages and safe retry this week:

- Server-render the public verification summary and minimize required JavaScript.
- Keep camera/MediaPipe code out of these routes; lazy-load optional images and avoid mandatory video.
- Paginate detailed history, compress API responses, and target summary JSON below 20 KB uncompressed.
- Preserve form input in memory during failures. Show explicit pending, failed, and completed states.
- Make import and review retries safe using idempotency and uniqueness enforcement. Reconcile an uncertain submission before asking users to submit again.
- Show a retryable connection state when current verification cannot be retrieved. Never present an offline result as freshly verified.

No persistent offline queue, sensitive local-storage cache, service worker, USSD, or SMS implementation this week. Assisted onboarding, language support, and support through local organizations belong in the inclusion pilot.

## 3. Discrepancies and required fixes

| Discrepancy                                                          | Resolution                                                                                                                                                                            |
| -------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Previous plan extended sign-in                                       | Remove that work entirely; flag authenticated browser access as a team dependency.                                                                                                    |
| Previous plan deferred all external history                          | Include historical ingestion and consented developer access now; defer former-customer attestation workflows.                                                                         |
| Previous plan required four sharing choices                          | Use a previewed standard summary and separate named-platform approval for details.                                                                                                    |
| Existing credential routes require user sessions                     | Add separate platform-authorized interfaces; do not expose worker session credentials to integrators.                                                                                 |
| One shared API key cannot identify companies                         | Add per-platform principals and isolation for the integration slice.                                                                                                                  |
| External platform IDs differ from our UUID                           | Add explicit, consent-backed mappings; do not weaken credential subject checks.                                                                                                       |
| API schema describes JWT, but runtime uses session cookies           | Document current behavior accurately without changing sign-in.                                                                                                                        |
| Imported history and verified credentials are conflated              | Preserve separate provenance and scoring eligibility.                                                                                                                                 |
| Reviews require protection, but historical jobs may lack it          | Keep historical evidence import separate from restricted reviews.                                                                                                                     |
| Trust UI displays unsupported metrics                                | Render supported evidence; distinguish confidence from performance.                                                                                                                   |
| Normalization currently breaks assessment                            | Consolidate the conflicting`normalise_db_row` definitions and make caller/input contracts consistent. Four targeted normalization/assessment tests currently fail at this boundary. |
| Missing ratings and unavailable signals may become misleading values | Preserve missing ratings and source coverage; validate scoring eligibility with the ML Engineer before publishing results.                                                            |

No code has been changed during this review.

## 4. Ownership and delivery order

| Owner                            | Responsibility                                                                                                                                                                               |
| -------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **You**                    | The three full-stack features, essential developer API slice, lightweight pages, integration example, feature migrations, and regression fixes needed by these flows.                        |
| **Software Engineer**      | Working authenticated worker/customer access; escrow, premium, completion and dispute records; platform credential/attestation review process; deployment and shared migration coordination. |
| **ML Engineer**            | Normalization contract review, source coverage, missing-rating behavior, imported starting-history calculation, preset validity, and scoring regression review.                              |
| **UI/UX Designer**         | Figma designs, summary preview, platform approval, evidence labels, and weak-network states.                                                                                                 |
| **Docs/Presentation Lead** | Revised product narrative, API examples, supported-versus-planned claims, and pilot measures.                                                                                                |

Sequence: stabilize normalization and agree API contracts → implement credentials → implement sharing → implement developer exchange → integrate restricted reviews → verify the complete journey.

This expands the previous weekly scope. A live end-to-end demo depends on timely authentication and protected-job evidence from the Software Engineer; those cannot be replaced with frontend badges.

## 5. Acceptance and validation

- **Credentials:** valid, tampered, expired, wrong-worker, malformed, oversized, and repeated imports; fresh export summary; atomic rollback.
- **Platform integration:** two isolated platform identities, explicit worker mapping, self-declared versus attested evidence, unauthorized access, revoked/expired grants, pagination, and idempotent retries.
- **Sharing:** correct standard summary, no private fields, current evidence updates, expiry, revocation, and named-platform consent for details.
- **Reviews:** eligible customer success; wrong customer, unverified identity, unprotected/platform job, missing confirmation, auto-release-only, dispute, duplicates, concurrency, and limiting failures.
- **Weak networks:** test throttled connections, interrupted responses, preserved in-session inputs, retry recovery, and absence of false success states. Check mobile layout at 360 px and verify on a representative low-cost Android device before claiming device support.
- **Regression:** fix the four observed failures; run backend tests, PostgreSQL migration/schema checks, frontend type checking/linting, and browser checks against Figma.

The weekly demonstration must show external history entering with honest provenance, a second platform accessing it after worker approval, a live summary being shared and revoked, and one eligible protected-job review being accepted.

For the later pilot, measure accepted records in real hiring decisions, verification cost, worker completion on low-cost devices, repeat use by employers, correction requests, and cutout rates. These results determine whether the proposed selling proposition holds.



# Implementation plan: your four weekly deliverables

## Core deliverables

| Task                                                                    | Implementation outcome                                                                                                                          |
| ----------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------- |
| **Anti-gamification review system — Restricted reviews**         | Customer review UI, backend eligibility checks, persistence, duplicate prevention, rate limits, and velocity checks.                            |
| **Credential import/export UI — Worker-facing**                  | Real signed exports, validated imports, source/verification labels, clear results, and refreshed worker records.                                |
| **Individual/off-platform verification — Shareable result page** | Lightweight public verification summary with live evidence, expiring links, revocation, and separate consent for detailed platform access.      |
| **API documentation — OpenAPI + examples**                       | Accurate contracts, authentication requirements, examples, errors, integration guidance, and testing instructions for everything you implement. |

The proposed product position remains: **portable, verifiable informal work history, accessible on low-cost devices and usable by integrating platforms.**

## Implementation decisions

### Restricted reviews

- Require the authenticated hiring customer, successful identity verification, explicit worker/customer completion confirmation, a completed outcome, and persisted protection evidence for an independent job.
- Block open disputes, unsupported customer attribution, failed/refunded protection, and duplicate reviews. Auto-release alone does not unlock reviews.
- Add eligibility and submission endpoints plus `/client/jobs/{id}/review`.
- Store reviewer, job, verification reference, integer rating from 1–5, optional comment up to 2,000 characters, and submission time.
- Enforce one review per job in the database. Apply five attempts/minute/user, thirty attempts/minute/IP, and ten successful reviews per reviewer over a rolling 24 hours.
- Persist review, outcome rating, and audit event atomically. Keep comments private and preserve existing scoring weights.

### Worker credential UI

- Add an authenticated worker-record endpoint and replace mocked data in the profile/portable-record flows.
- Connect export to the existing signed bundle endpoint, refreshing assessment before export.
- Support importing a JSON bundle or pasted token, with validation errors, duplicate handling, imported-count feedback, and record refresh.
- Keep verified credentials separate from self-declared historical evidence.
- Display real bands, evidence confidence, provenance, and timestamps. Remove unsupported score percentages and punctuality metrics from these live flows.
- Preserve worker-bound token checks and seven-day expiry. Receiving platforms calculate their own assessment from eligible evidence.

### Shareable verification result

- Use **Share verification → preview → generate link**, without mandatory scope checkboxes.
- Share a standard summary: approved display name, role/general area, identity status, trust assessment, aggregate evidence counts, and supported guarantor status.
- Exclude client identities/contact details, identity numbers/documents, provider references, credential tokens, and detailed allegations.
- Add owner create/list/revoke endpoints, a share-grant table with hashed random tokens, and public `/verify/{token}`.
- Links show current evidence, expire after seven days, and support immediate revocation. Add copy-link and WhatsApp sharing.
- Use uncached responses, `noindex`, restrictive referrer handling, and token-redacted logs.
- Detailed history requires separate approval for a named platform.

### Supporting developer integration

- Add worker-approved platform grants, platform-worker identity mappings, historical ingestion, and paginated history access.
- Interfaces: platform worker-link creation, history import/read, worker grant management, and grant-authorized access to existing `/trust/query`.
- Use hashed, revocable per-platform API keys. Existing shared-key compatibility remains development-only and cannot authorize the new history interfaces.
- Deduplicate records by worker, authoritative source, and source record ID. Support idempotent retries; reject changed payloads reusing a key.
- An API submission does not establish verification. Only reviewed platforms with explicit attestation authority may attest their own records.
- Preserve provenance and distinguish verified evidence from self-declared history. Keep prior-customer attestation workflows outside this week.
- Supply a small two-platform example; do not build a full SDK.

### Weak-network support

- Server-render public summaries, minimize JavaScript, lazy-load optional images, and keep camera/MediaPipe dependencies out of these routes.
- Compress responses, paginate history, and target summary JSON below 20 KB uncompressed.
- Preserve inputs in memory during failures and reconcile uncertain submissions before retrying.
- Do not claim fresh verification offline. Persistent offline queues, sensitive device caches, SMS, and USSD remain future work.

### Clean documentation for all your work

- Generate accurate OpenAPI descriptions from request/response schemas.
- Document authorization, consent, ownership, provenance, pagination, expiry, revocation, idempotency, and rate limits.
- Include successful and failed request examples for reviews, credentials, sharing, grants, historical import/access, and trust queries.
- Provide examples for tampered/expired credentials, duplicates, ineligible reviews, unauthorized platforms, revoked grants, and retryable failures.
- Add a developer walkthrough demonstrating history exchange between two platform contexts.
- Explain current session-cookie authentication accurately; correct the existing JWT documentation discrepancy.
- Include local setup/testing commands and clearly identify sandbox behavior, external dependencies, and interoperability limits.

## Dependencies and discrepancies

**Authentication remains outside your implementation scope:** do not extend email-code sign-in, registration, or seeded-account login. Reuse valid existing sessions; working worker/customer browser access is a Software Engineer dependency.

Before feature integration, fix the conflicting `normalise_db_row` definitions and align callers with one input contract. Four targeted normalization/assessment tests currently fail there.

| Owner                            | Required work                                                                                                                                                                  |
| -------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **You**                    | Four deliverables, supporting API slice, feature migrations, lightweight behavior, and necessary regression fixes.                                                             |
| **Software Engineer**      | Authenticated access, customer attribution, authoritative protection/completion/dispute records, platform attestation approval, deployment, and shared migration coordination. |
| **ML Engineer**            | Normalization review, missing ratings/signals, provenance-aware scoring eligibility, imported starting-history behavior, and scoring regression review.                        |
| **UI/UX Designer**         | Figma designs and accessible loading/error/empty/consent states.                                                                                                               |
| **Docs/Presentation Lead** | Review product claims, demo narrative, and supported-versus-planned capabilities.                                                                                              |

Historical jobs without protection can be imported as evidence; they do not qualify for protected-job reviews. Revoking access prevents future retrieval but cannot recall downloaded records.

## Delivery and acceptance

Sequence: stabilize normalization/contracts → credentials → sharing → platform integration → restricted reviews → integration verification. Update documentation alongside each feature.

Verify credential integrity and duplicate handling; platform isolation, consent and revocation; private-field exclusion; review eligibility, concurrency and limits; and interrupted-network recovery.

Run backend tests, PostgreSQL migration/schema checks, frontend type checking/linting, and browser checks against Figma. Test at 360 px and on a representative low-cost Android device before claiming device support.

Completion means all four deliverables work together: history enters with honest provenance, a second platform accesses approved evidence, a worker shares and revokes a live summary, one eligible review succeeds, and another developer can reproduce the flows using your documentation.
