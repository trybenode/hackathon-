# Developer sandbox

Sandbox credentials work against the same API as production, but they can only reach a fixed set of demo workers. Production credentials can never reach the demo workers, and sandbox credentials can never reach real ones (`403 ENVIRONMENT_MISMATCH`).

## Getting credentials

1. Sign up on the developer page with your work email.
2. Complete both verification steps (identity, then business). An operator reviews them; until then credentials stay locked.
3. Once approved, choose **Generate API credentials → Sandbox**. Copy the secret straight away: it is shown once. Send it as the `X-API-Key` header.

## Demo workers

Each demo worker has a fixed history shaped to land in one trust band, so the same call always gets the same answer. Link one with its consent token; any external id you choose works.

| Worker | Role | Band | Guarantor | Consent token |
| --- | --- | --- | --- | --- |
| Ada Okafor | Cleaner | High | active | `sandbox-consent-ada-demo-worker-token` |
| Tunde Bello | Electrician | Medium | pending | `sandbox-consent-tunde-demo-worker-token` |
| Bisi Adeyemi | Plumber | Low | expired (none) | `sandbox-consent-bisi-demo-worker-token` |
| Chidi Eze | Painter | Building History | none | `sandbox-consent-chidi-demo-worker-token` |

All four have passed identity and liveness checks.

The dashboard API (`GET /api/v1/me/developer`) lists the same workers under `sandbox_workers`.

## First calls

```bash
# 1. Link a demo worker to an id in your system; the response carries the worker_id.
curl -X POST "$API/api/v1/platform/worker-links" \
  -H "X-API-Key: $SANDBOX_SECRET" -H "Content-Type: application/json" \
  -d '{"external_worker_id": "user-42", "consent_token": "sandbox-consent-ada-demo-worker-token"}'

# 2. Ask for a trust assessment.
curl -X POST "$API/api/v1/trust/query" \
  -H "X-API-Key: $SANDBOX_SECRET" -H "Content-Type: application/json" \
  -d '{"worker_id": "<worker_id>", "platform_type": "generic", "job_context": {"job_type": "cleaning", "value_band": "low"}}'

# 3. Read the worker's history.
curl "$API/api/v1/platform/workers/user-42/history" -H "X-API-Key: $SANDBOX_SECRET"
```

## What the trust query tells you

Besides the decision, confidence and band, every trust query returns what has been verified about the worker. It never includes identity numbers or documents.

```json
"verification": {
  "identity": "verified",
  "liveness": "verified",
  "guarantor": "active",
  "guarantor_valid_until": "2027-08-07T10:00:00Z"
}
```

`identity` and `liveness` are `verified`, `sandbox` (passed with a stand-in provider) or `not_verified`. `guarantor` is `active`, `pending` or `none`.

## Guarantees

With the worker's approval you can work with their guarantees:

- `GET /guarantor-instruments?worker_id=…` lists a worker's guarantees (needs approval to read).
- `POST /guarantor-instruments` asks a person to stand behind a worker (needs approval to write).
- `POST /guarantor-instruments/{id}/send | trigger | resolve | revoke` work only on guarantees your platform asked for.
- `GET /guarantor-instruments` without a worker lists the guarantees your platform asked for.

## Your own scoring settings

Each platform can set its own weights, thresholds and rules per platform type. Settings belong to the key's environment, so sandbox experiments never change production scores.

- `GET /platform/scoring-config` returns the settings for every platform type (`custom: false` while the preset applies) and the signals you can use.
- `PUT /platform/scoring-config/{platform_type}` saves your settings. Weights must add up to 1 and thresholds must satisfy 0 < medium < high ≤ 1.
- `DELETE /platform/scoring-config/{platform_type}` goes back to the preset.

```bash
curl -X PUT "$API/api/v1/platform/scoring-config/domestic" \
  -H "X-API-Key: $SANDBOX_SECRET" -H "Content-Type: application/json" \
  -d '{"weights": {"completion_rate": 0.4, "dispute_rate": 0.3, "no_show_rate": 0.3}, "required_signals": ["completion_rate"], "min_jobs": 10, "high_threshold": 0.85, "medium_threshold": 0.65}'
```

## Changes in the sandbox

History imports and guarantee changes run in full and answer exactly as production would, but nothing is kept: the demo workers are shared by every developer, so their histories and guarantees never change.

## Usage

Every call made with your keys is counted on the dashboard (total and successful calls) and the latest ones are listed. Only the method, route, status and duration are recorded: no request bodies, headers or worker ids.
