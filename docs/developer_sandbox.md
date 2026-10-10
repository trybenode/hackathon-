# Developer sandbox

Sandbox credentials work against the same API as production, but they can only reach a fixed set of demo workers. Production credentials can never reach the demo workers, and sandbox credentials can never reach real ones (`403 ENVIRONMENT_MISMATCH`).

## Getting credentials

1. Sign up on the developer page with your work email.
2. Complete both verification steps (identity, then business). An operator reviews them; until then credentials stay locked.
3. Once approved, choose **Generate API credentials → Sandbox**. Copy the secret straight away: it is shown once. Send it as the `X-API-Key` header.

## Demo workers

Each demo worker has a fixed history shaped to land in one trust band, so the same call always gets the same answer. Link one with its consent token; any external id you choose works.

| Worker | Role | Band | Consent token |
| --- | --- | --- | --- |
| Ada Okafor | Cleaner | High | `sandbox-consent-ada-demo-worker-token` |
| Tunde Bello | Electrician | Medium | `sandbox-consent-tunde-demo-worker-token` |
| Bisi Adeyemi | Plumber | Low | `sandbox-consent-bisi-demo-worker-token` |
| Chidi Eze | Painter | Building History | `sandbox-consent-chidi-demo-worker-token` |

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

## Imports in the sandbox

`POST /platform/workers/{external_id}/history/import` runs in full and answers exactly as production would, but nothing is kept: the demo workers are shared by every developer, so their histories never change.

## Usage

Every call made with your keys is counted on the dashboard (total and successful calls) and the latest ones are listed. Only the method, route, status and duration are recorded: no request bodies, headers or worker ids.
