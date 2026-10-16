# Customer attribution, language access and unscored history

The worker documents work in a chosen language, reviews the details, asks the intended customer to respond, and shares aggregate evidence. This slice supports completed/released jobs already in the system and separate informal claims. Other-platform integration is excluded from this pilot UI; existing platform APIs remain compatible.

Detailed plans prepared before implementation: [attribution](iterations/01-customer-attribution.md), [page localization](iterations/02-core-localization.md), [voice drafts](iterations/03-voice-history.md), [clarification](iterations/04-translated-clarification.md), [integration/pilot](iterations/05-record-sharing-and-pilot.md), [conditional escrow](iterations/06-escrow-corroboration.md).

## Evidence and authentication

| Displayed evidence                                    | Establishes                                                                  | Does not establish                                                     |
| ----------------------------------------------------- | ---------------------------------------------------------------------------- | ---------------------------------------------------------------------- |
| Self-declared history                                 | Worker approved this revision                                                | Independent verification or protected completion                       |
| Contact verified; hiring relationship not established | Intended contact passed the challenge                                        | Customer declaration, actual hiring relationship or completed work     |
| Contact verified; customer relationship declared      | Intended contact controls the phone and explicitly responded                 | Actual historical hiring relationship                                  |
| Sandbox confirmation                                  | Development code was accepted                                                | SMS delivery or real contact verification                              |
| Matched hiring customer                               | Existing account matches both request recipient and current`Job.client_id` | KYC, payment protection, satisfaction or restricted-review eligibility |
| Identity check: Sandbox / Verified / Not verified     | Separate latest identity evidence                                            | Customer/job relationship                                              |
| Payment corroboration: unavailable                    | No authenticated payer/customer mapping exists yet                           | Any escrow-backed attribution                                          |

Owner `/me/*` resources use the existing `guarantor_session` cookie. They do not use JWTs, create accounts or extend email-code sign-in. System jobs require an existing active hiring-customer session; a different account cannot read the claim or respond. Missing attribution blocks request creation. Changing the job/customer mapping invalidates current matching and removes the old response from current claim/count presentation. Historical receipts remain auditable.

Informal links identify a request but authorize no private claim content. The API shows only masked destination digits until the stored intended phone passes a challenge. `history_recipient` is HttpOnly, SameSite=Lax, Secure outside development, scoped to the API history-confirmation path and one request, for at most 30 minutes. It is never a general account session. The UI never accepts a new destination from the recipient. General browser sign-in/customer availability remains the Software Engineer's dependency.

## Text journey and revision lifecycle

1. Open `/worker/profile/record/history` from the portable record. Select informal work or an owned completed/released job; enter work type, description, approximate date and general area. System titles/completion facts come from the job, not submitted guesses. Approve/save.
2. Preview the confirmation request and intended contact, then generate a seven-day link. Copy or share via WhatsApp explicitly; the application sends no WhatsApp messages itself.
3. Recipient opens `/confirm-work/{token}`, matches the hiring account or verifies the intended phone, reads original details, optionally asks clarification, and explicitly chooses confirmed, incorrect, or unrecognized with recording consent. Confirmation also requires a customer declaration.
4. Worker sees the response method/time, can correct details or archive the claim, and manages/revokes requests. Corrections increment the revision and revoke all prior access. Prior-revision confirmations cease to count. Recipient withdrawal is available through an authorized, unexpired request and removes active attestation without erasing audit.
5. Refresh the portable record, preview the public summary, generate/open/revoke an existing public share. It contains counts only for this history slice, never customer contacts, claims, conversations, recordings or transcripts.

A negative response does not open a dispute or create a negative rating. Neither approval, response, contact check, message nor translation writes `NormalizedOutcome`, changes `Job.status`, changes starting history, adds a protected completion confirmation, or qualifies a restricted review. Claims are excluded from signed verified-outcome exports and platform-history exchange.

Counts distinguish self-declared informal jobs, genuine contact attestations, sandbox confirmations and matched-account confirmations. They use current unarchived revisions and non-withdrawn confirmed responses.

System-job annotations never add another completed-job count. Link revocation/expiry removes retrieval access; it does not rewrite a previously recorded response. Archive, correction or response withdrawal removes its active evidence count.

## API contracts and recovery

Generated contracts: [OpenAPI](openapi.json). Ready-to-edit requests: [history examples](history_examples.http).

| Resource                     | Routes                                                                                                                                                              |
| ---------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Worker job choices           | `GET /me/history-jobs?page=1&size=20`                                                                                                                                     |
| Claims                       | `POST/GET /me/history-claims`, `GET/PATCH/DELETE /me/history-claims/{id}`                                                                                       |
| Request creation/listing     | `POST/GET /me/history-claims/{id}/confirmation-requests`                                                                                                          |
| Revoke capability            | `DELETE /me/confirmation-requests/{id}`                                                                                                                           |
| Recipient access             | `GET /history-confirmations/{token}`                                                                                                                              |
| Contact challenge            | `POST /history-confirmations/{token}/challenge`, `POST .../challenge/check`                                                                                     |
| Explicit response/withdrawal | `POST/DELETE /history-confirmations/{token}/response`                                                                                                             |
| Voice                        | `GET /me/history-capabilities`, `POST /me/history-drafts`, `GET /me/history-drafts/{id}`, `POST .../{id}/retry`, `POST .../{id}/save`                     |
| Private thread               | `GET/POST /me/history-claims/{id}/messages` and `GET/POST /history-confirmations/{token}/messages`                                                              |
| Derivative translation       | `POST .../messages/{id}/translations`; recipient `POST .../description-translation`                                                                             |
| Creation receipts            | `GET /me/history-claims/operations/{uuid}`, `GET /me/history-drafts/operations/{uuid}`, `GET /me/history-claims/{id}/confirmation-requests/operations/{uuid}` |
| Message receipts             | `GET .../messages/operations/{uuid}` for the authenticated participant                                                                                            |

All routes above use the configured `/api/v1` prefix. Lists use items/total/page/size/pages, default 20 and cap 100. Create claim, request, recording and message operations require `Idempotency-Key` UUIDs. Same key/body returns the existing receipt; changed bodies conflict. Approval reuses the draft ID atomically. PATCH requires the current revision; uncertain corrections first read the latest claim and compare the proposed fields. Responses allow one final receipt per request; one claim revision cannot solicit another final response without an explicit correction.

Inputs remain in memory, with stable operation/body snapshots during unknown network or server errors. Read a receipt first; only `OPERATION_NOT_FOUND` permits repeating the same write. A lost request token is unrecoverable because only its hash is stored: revoke that request before replacing it. GET recipient access reconciles response submissions. Confirm a revocation acknowledgement before replacing a secret. There is no persistent browser queue, sensitive local storage or fresh-offline-verification claim. Navigating away/reloading can discard unsaved inputs.

Consistent failures contain `detail` and `code`; 429/limiter failures have Retry-After. Redis enforces 30 attempts/minute/IP and five mutations/minute/session. Failure to reach Redis fails closed. Request delivery is limited to 10/day/worker; a request permits five SMS deliveries, a 60-second resend interval and five checks per 10-minute challenge. Voice is limited to 5 MB/60 seconds, two pending tasks and 20 uploads/day/worker. Production deployments must independently configure SMS provider fraud/cost controls and monitor abuse.

Common failures: `CUSTOMER_ACCOUNT_REQUIRED`, `CONTACT_VERIFICATION_REQUIRED`, `CODE_INVALID`, `CHALLENGE_UNAVAILABLE`, `CHALLENGE_SEND_LIMIT`, `CLAIM_REVISION_CHANGED`, `RESPONSE_EXISTS`, `IDEMPOTENCY_CONFLICT`, `LINK_UNAVAILABLE`, `ORIGIN_REJECTED`, `HISTORY_RATE_LIMIT`, `LIMITER_UNAVAILABLE`, `MODEL_UNAVAILABLE`, `TRANSLATION_VALUES_CHANGED`. A 403/410 or explicit validation conflict requires correcting authorization/input rather than creating a new retry operation.

## Language and voice configuration

English, Yoruba, Hausa and Igbo dictionaries are source-controlled candidate copy. Only the chosen dictionary is selected by the server; a non-sensitive locale cookie preserves existing URLs and independent worker/customer preferences. Buttons, consent, attribution labels and core errors are not machine-translated at runtime. Non-English UI displays the pending-review notice; untranslated strings remain explicitly English. User messages remain in their original language. This is pilot localization, not native-language approval or complete localization of all existing screens.

Original job messages are authoritative. Requested N-ATLAS translations are separate model/revision-labelled derivatives; failures preserve originals. The adapter rejects dropped/changed numeric/contact/URL/identifier tokens, but that check does not prove correct negation or meaning. Translation never changes agreed terms or confirms work. Correctionsequire a revised claim and another explicit response. Live chat has only a disabled interface and a test fixture; there is no simulated presence, notification or delivery.

The official [N-ATLAS model card](https://huggingface.co/NCAIR1/N-ATLaS) lists English/Hausa/Igbo/Yoruba and requires model access/terms acceptance. The [official model catalogue](https://huggingface.co/NCAIR1) contains the ASR models used here. The optional gateway is a self-hosted adapter for these official models, not a claim that an official hosted ASR endpoint is already provisioned. SMS uses [Twilio Verify](https://www.twilio.com/docs/verify/api/verification-check) and checks the stored verification reference and contact. Delivery/hosting credentials and model terms remain operator dependencies.

Normal development keeps `HISTORY_AI_ENABLED=false`, `SMS_PROVIDER=stub`. Stub codes are shown only in development, never logged or accepted as production verification. Production must set `SMS_PROVIDER=twilio` and all three Twilio configuration values, configure six-digit Verify codes, deliver/test to Nigerian numbers, serve the API over HTTPS and permit its frontend origin.

For voice, install ffmpeg/ffprobe and configure a private shared runtime directory visible to API and worker. Never use a public/static directory. After configuring the authenticated model gateway:

```bash
cd backend
.venv/bin/alembic upgrade head
.venv/bin/uvicorn app.main:app --port 8000
# Separate terminal/process, same database + private spool:
.venv/bin/python -m scripts.history_worker
```

The durable PostgreSQL worker claims rows with leases/skip-locked acquisition and does not hold a DB transaction while calling models. Task attempts are bounded at three; failed tasks preserve audio for authorized retry until expiry. Audio is private, filename-randomized and permission-restricted; ffprobe validates actual media and ffmpeg decodes local files to mono 16 kHz. No external audio URLs are fetched. Audio is deleted after processing; saving clears transient transcript/draft fields. Expiry reads and the worker sweep enforce the 24-hour retention target and remove crash leftovers. Keep the worker running and monitor sweep health; stopping it can delay physical deletion. Approved claim descriptions remain intentional worker records.

Optional separate model environment (no heavyweight libraries added to the application environment):

```bash
cd backend
python3.12 -m venv .venv-history-models
.venv-history-models/bin/pip install -r requirements-history-models.txt
# Export HF_TOKEN after obtaining model access, and HISTORY_GATEWAY_KEY privately.
.venv-history-models/bin/uvicorn scripts.history_model_gateway:app --host 127.0.0.1 --port 8091
```

Set `HISTORY_AI_ENABLED=true`, `HISTORY_AI_BASE_URL` to the gateway and `HISTORY_AI_API_KEY` to that gateway key in the application environment. Local HTTP is development-only; production requires HTTPS and a non-empty key. The worker sends ASR `/asr`, extraction `/extract` and translation `/translate`; model identity/output schemas are checked, and unknown revisions remain unknown. Gateway compute and dependencies were not installed or evaluated in this implementation session. Use suitable CPU/GPU resources and evaluate the actual language pairs; there is no silent fallback to another model. Re-recording, file upload and manual text entry are available alternatives. Approved spoken instruction assets remain a language-review dependency.

## Setup, checks and rollout

Existing login is unchanged: use valid sessions provided by the authentication implementation. For isolated development, configure disposable PostgreSQL + Redis as described in [local development](local_development.md); do not run destructive test fixtures against the shared deployment.

```bash
cd backend
.venv/bin/pytest -q
.venv/bin/python scripts/export_openapi.py
.venv/bin/alembic heads
# With TEST_DATABASE_URL pointing only to isolated local/CI PostgreSQL:
.venv/bin/python scripts/check_migration_paths.py
.venv/bin/alembic upgrade head
.venv/bin/python scripts/check_migrations.py
# Set TEST_REDIS_URL to an isolated test Redis database for live limiter checks.
# Set TEST_DATABASE_URL to run PostgreSQL concurrency regressions.
```

```bash
cd frontend
pnpm typecheck
pnpm lint
pnpm build
# Alternative when the local Turbopack environment cannot bind its build port:
pnpm exec next build --webpack
```

Additive migrations follow `c735ab42f6d0` → `a81c2d43e9f0` → `a82c2d43e9f1` → `a83c2d43e9f2`. Existing revisions are preserved. `HISTORY_ENABLED=false` disables new history APIs; `HISTORY_AI_ENABLED=false` disables new inference. Production SMS stubs fail closed. Platform approval UI is hidden unless explicitly opted in using `NEXT_PUBLIC_PLATFORM_APPROVALS_ENABLED=true`; no new external-platform history routes were added. Disable features and coordinate data-safe rollback with Software; downgrades remove new tables and must not be applied to valued records casually.

Public summaries use server rendering, no-store/noindex/no-referrer and existing compression; API and Next access logs redact or omit secret paths. Review upstream/reverse-proxy logs separately. Camera/MediaPipe code is absent from new history/public routes. No physical device performance, visual approval, language comprehension, real SMS delivery or payment corroboration is claimed by isolated tests.

See [validation](history_validation.md) and [team handoff](integration_handoff.md) for actual results and open release gates.

## Worker page localization and private translated speech

The worker layout exposes English/Yoruba/Hausa/Igbo selection across dashboard,
job management, profile, notifications and record dialogs. Static candidate
copy uses typed dictionaries; missing translations and unknown provider strings
fall back to English. Names, addresses, job titles and original message contents
remain unchanged. Native review is pending. `/sign-in?next=/worker/...` localizes
its presentation without changing account authentication. Guarantor-wide
localization is outside this stage.

The existing clarification thread keeps the original and N-ATLAS translation
separate. Translate first, then request Listen. Speech is disabled by default.
The existing worker processes durable voice and speech tasks:

```bash
make dev-voice
```

Configure `HISTORY_SPEECH_ENABLED`, `HISTORY_SPEECH_BASE_URL`,
`HISTORY_SPEECH_API_KEY`, `HISTORY_SPEECH_MODEL`, `HISTORY_SPEECH_VERSION`, and
`HISTORY_SPEECH_LANGUAGES` only after validating actual language voices.
The speech gateway is separate from the N-ATLAS text gateway. It must implement
`POST /synthesize` with bearer authentication and JSON
`{text, language, model, version}`. It returns MP3 bytes (`audio/mpeg`) with
`X-Speech-Language`, `X-Speech-Model` and `X-Speech-Version` matching the request.
Production requires HTTPS. Responses are bounded at 5 MB and 60 seconds.
No real provider, pronunciation or native review is claimed by adapter tests.

Worker speech routes:

- `GET /me/history-speech-capabilities`
- `POST /me/history-claims/{claim_id}/messages/{message_id}/audio` with `{ "target": "yo" }`
- `GET .../audio/{audio_id}` for status
- `GET .../audio/{audio_id}/content` for authenticated MP3 bytes

Recipient equivalents use `/history-confirmations/{token}/messages/{message_id}`
and the existing account/contact scope. `GET /history-confirmations/{token}/speech-capabilities`
requires the same authorization. Public summaries contain neither audio nor conversations.
Creation returns 202 and a status object with id, language, status, model,
version, expires_at and error_code. Repeat requests for the same translation
reuse the task; failed/expired tasks can be retried explicitly. Queued/processing
status is reconciled through GET, without resubmitting a message. Generation
requires a ready translation (409 `TRANSLATION_REQUIRED`); an unsupported voice
returns 503 `SPEECH_UNAVAILABLE`. Rate limits and current confirmation requirements
remain unchanged. Expired, revoked, superseded or unauthorized recipient access
cannot retrieve audio. Files expire after 24 hours and are swept by the worker.
Native audio controls load authenticated blobs only on request, never autoplay,
and release object URLs on unmount. Access revocation cannot recall bytes already
retrieved by a participant.

The additive merge revision joins history and escrow heads before creating the
speech table. Apply `alembic upgrade head` to the selected development database.
Rollback/disable speech configuration to stop new audio generation; keep text
history and translations available.

## Direct Spitch playback adapter

Configure your private development environment; never commit the key:

```dotenv
HISTORY_SPEECH_PROVIDER=spitch
HISTORY_SPEECH_ENABLED=true
HISTORY_SPEECH_API_KEY=<your Spitch API key>
HISTORY_SPEECH_MODEL=spitch-managed-tts
HISTORY_SPEECH_VERSION=pilot-voice-config-1
HISTORY_SPEECH_LANGUAGES=en,yo,ha,ig
HISTORY_SPEECH_VOICES='{"en":"john","yo":"sade","ha":"amina","ig":"ngozi"}'
```

These voices are candidates for development evaluation, not native-reviewed production approval. Enable only reviewed languages in production. Missing/invalid voice entries disable those languages. BASE_URL is unused for Spitch; its adapter calls the fixed HTTPS endpoint with exact translated text and MP3 output using the existing async HTTP client.

MODEL and VERSION identify our managed-provider/configuration revision, not a verified upstream model revision: the documented API does not return one. Increment VERSION when revising configuration. Provider/model/version/voice changes invalidate prior audio. Existing queue, current-thread access checks, private storage and 24-hour expiry apply.

Configure the translation gateway too, then run `make dev-voice` from the repository root. Translate a thread message, choose Listen and refresh processing status. Real credentials, delivery/latency/cost checks and native-language pronunciation review remain external gates; mocked tests establish no real-provider success. Static page copy continues to use dictionaries.

Sources: [speech API](https://docs.spitch.app/features/speech), [voice roster](https://docs.spitch.app/concepts/voices).


## Live N-ATLAS deployment

See [GPU gateway, Vercel storage and external jobs](natlas_deployment.md) for
actual inference setup and live acceptance. The code supports private S3 audio
handoff to external workers; no GPU host or live benchmark is claimed.
