# Dynamic Trust Infrastructure - B2B API Schema

Base URL: `/api/v1`

Authentication:

- Platform routes use an API key in `X-API-Key`.
- User-facing routes use the existing HTTP-only `guarantor_session` cookie.
- Dedicated platform keys identify organizations; history and assessment access require worker approval. The legacy shared key is limited to development trust queries.

Implemented portability, consent, restricted reviews, examples and handoff: [portable work history guide](docs/portable_work_history.md). Generated contract: [OpenAPI JSON](docs/openapi.json). Monitoring/configuration/job-provider endpoints described below remain design contracts unless registered in the generated OpenAPI schema.

## API Purpose

The Platform API has three primary purposes:

1. **Onboarding trust assessment**: decide whether a worker can start offering a service.
2. **Continuous monitoring and risk flagging**: track a worker after onboarding and expose changing risk.
3. **Portable credentials**: move verified work history and trust records between platforms.

Supporting capabilities are normalization, configurable policies, outcome ingestion, personal guarantors, independent-job escrow, and audit history.

## 1. Onboarding Trust Assessment

### `POST /trust/query`

Run a full onboarding or new-service-category assessment.

Request:

```json
{
  "worker_id": "uuid",
  "platform_type": "domestic",
  "job_context": {
    "job_type": "cleaning",
    "value_band": "low"
  }
}
```

Response:

```json
{
  "worker_id": "uuid",
  "decision": true,
  "confidence": 0.84,
  "band": "High",
  "status": "Scored",
  "signals_used": ["completion_rate", "dispute_rate", "repeat_hire_rate"],
  "explanation_summary": "Strong completion history with very low disputes",
  "platform_type_applied": "domestic"
}
```

Trust bands are `High`, `Medium`, `Low`, and `Building History`. A new worker with insufficient evidence must receive `Building History` rather than a fabricated score.

The current endpoint scores persisted, normalized, verified outcomes only. It does not accept caller-supplied aggregate signals. Outcome ingestion and this endpoint must call the same `assess_worker(session, worker_id, platform_type)` service so a score is consistent across both paths. An unchanged input/configuration fingerprint reuses the existing assessment.

### `POST /trust/configure`

Configure platform-specific baselines, thresholds, and weights.

```json
{
  "platform_id": "uuid",
  "platform_type": "domestic",
  "baselines": {
    "min_completion_rate": 0.85,
    "max_dispute_rate": 0.05,
    "min_jobs_for_scoring": 5
  },
  "weights": {
    "completion_rate": 0.35,
    "dispute_count": 0.25,
    "repeat_hires": 0.20,
    "average_rating": 0.15,
    "no_shows": 0.05
  }
}
```

## 2. Continuous Monitoring and Risk Flagging

### `GET /workers/{worker_id}/monitoring`

Return the worker's current post-onboarding standing.

```json
{
  "worker_id": "uuid",
  "decision": true,
  "confidence": 0.84,
  "band": "High",
  "risk_status": "clear",
  "under_investigation": false,
  "active_flags": [],
  "last_assessed_at": "2026-09-19T21:00:00Z"
}
```

Risk statuses are `clear`, `flagged`, `under_investigation`, `malicious`, and `high_risk`.

### `POST /workers/{worker_id}/monitoring/flags`

Create a verified risk flag.

```json
{
  "type": "negative_outcome",
  "severity": "high",
  "reason": "Repeated disputed outcomes",
  "source": "platform",
  "investigation_required": true
}
```

Flag types are `negative_outcome`, `dispute_pattern`, `identity_concern`, and `manual_review`. Severity is `low`, `medium`, `high`, or `critical`.

### `POST /workers/{worker_id}/monitoring/investigate`

Start an investigation.

```json
{
  "reason": "Repeated verified complaints",
  "reference": "case-123"
}
```

### `POST /workers/{worker_id}/monitoring/status`

Record an explicit risk-status transition.

```json
{
  "status": "high_risk",
  "reason": "Investigation confirmed material risk",
  "source": "operator"
}
```

`malicious` and `high_risk` require an explicit reason and source. They must not be inferred from an unverified client assertion.

### `GET /workers/{worker_id}/monitoring/history`

Return historical statuses and flags. Supports `page`, `size`, and `cursor` pagination.

```json
{
  "items": [
    {
      "status": "high_risk",
      "reason": "Investigation confirmed material risk",
      "source": "system",
      "created_at": "2026-09-19T21:00:00Z",
      "created_by": "uuid"
    }
  ],
  "total": 1,
  "page": 1,
  "size": 20,
  "pages": 1
}
```

### `POST /workers/{worker_id}/monitoring/subscribe`

Register a platform webhook for new negative outcomes and status changes.

```json
{
  "callback_url": "https://platform.example/webhooks/trust",
  "event_types": [
    "negative_outcome",
    "risk_status_changed",
    "investigation_started"
  ]
}
```

New negative outcomes invalidate cached trust summaries and notify active subscribers where configured.

## 3. Portable Credentials

### `GET /workers/{worker_id}/credentials/export`

Export verified work history and the current trust record.

The response contains `worker_id`, `exported_at`, a `trust_summary`, `verified_outcomes`, and an expiring HMAC-signed `credential_token`. The token is bound to the same worker ID and expires after seven days. Only verified outcomes are included.

### `POST /workers/{worker_id}/credentials/import`

Import a signed or short-lived credential token from another platform.

```json
{
  "credential_token": "signed-token",
  "source_platform": "platform-name"
}
```

Imports must validate the token, preserve source and issuer metadata, avoid duplicate outcomes, and trigger reassessment when new evidence is accepted.
The basic implementation accepts only bundles signed by this service and bound to the authenticated worker. User-uploaded CSV history remains unverified and must not be promoted to verified evidence by this endpoint.

## Supporting Capabilities

### `POST /outcomes`

Accept platform history, retain the original payload, normalize it, and feed the assessment and monitoring pipelines.

```json
{
  "worker_id": "uuid",
  "job_id": "uuid",
  "platform_id": "uuid",
  "platform_type": "domestic",
  "outcome": {
    "status": "completed",
    "rating": 4.5,
    "completion_confirmed": true,
    "quality_flags": ["on_time"],
    "dispute_reason": null,
    "evidence_urls": [],
    "completed_at": "2026-09-19T18:30:00Z"
  },
  "raw_payload": {}
}
```

Outcome statuses are `completed`, `cancelled`, `disputed`, and `no_show`.

### Personal Guarantors

- `POST /guarantors/instruments`
- `POST /guarantors/instruments/{instrument_id}/sign`
- `GET /guarantors/instruments/{instrument_id}`

A guarantor is always a real person. Electronic signatures record signer identity, timestamp, IP address, and user-agent.

### Independent-Job Escrow

- `POST /independent/jobs/{job_id}/escrow`
- `POST /independent/jobs/{job_id}/escrow/confirm-premium`
- `GET /independent/jobs/{job_id}/escrow`

These routes must reject jobs linked to a platform. Escrow and micro-insurance use Vesti and are not available for platform-backed jobs.

### Job Completion

- `POST /jobs/{job_id}/confirm`
- `POST /jobs/{job_id}/dispute`

Completion uses dual confirmation, auto-release, and dispute hold. Confirmation and risk transitions must be auditable.

### Worker Summary

`GET /workers/{worker_id}/summary` returns the current trust decision, confidence, band, risk status, aggregate statistics, and whether an active guarantor exists.

## Error Contract

All errors use:

```json
{
  "detail": "Human readable message",
  "code": "INVALID_INSTRUMENT_STATUS"
}
```

## Implementation Rules

- Use Pydantic models for every request and response.
- Keep normalization in a dedicated service before scoring.
- Keep monitoring status history append-only.
- Write audit events for status, investigation, guarantor, credential, escrow, and dispute changes.
- Invalidate trust caches after outcome writes and policy changes.
- Apply pagination to all list endpoints.


## Integrated worker and review interfaces

The canonical session-authenticated worker snapshot is `GET /me/record`.
Full history uses `GET /me/record/history?page=1&size=20`; the older
`GET /me/worker/record` remains a compatibility projection. Both use shared
identity, guarantor, assessment and evidence semantics. Private worker screens
retain model score separately from evidence confidence. Self-declared history
is separate from verified outcomes; absent ratings/metrics remain null.
Customer review entry uses `GET /me/client/jobs` and `/client/jobs` in the web UI.

Share/platform-grant creation accepts an optional UUID `Idempotency-Key`.
Worker-owned `.../operations/{operation_id}` endpoints reconcile lost responses
without recovering secret tokens. See the integration guide and generated
OpenAPI for all request/response fields, examples, errors and security requirements.
