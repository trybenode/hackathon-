# Free Render demo

Use [render.free.yaml](../render.free.yaml) for a text-based demonstration.
The paid production Blueprint remains [render.yaml](../render.yaml).

The free profile creates two Docker web services and one free Key Value instance.
Use an isolated Neon Free database/project for durable PostgreSQL records. It
does not provision a PostgreSQL account or change an existing database.

## Setup

1. Commit/push the free Blueprint and application files to your deployment branch.
   In Render's New Blueprint setup, set **Blueprint Path** to `render.free.yaml`.
   Do not sync this over an existing valued paid deployment: this profile uses
   separate `trust-demo-*` service names.
2. Supply the isolated demo database URL, direct migration URL, verified Resend
   sender/key and intended frontend HTTPS origin. Signing/proxy keys are generated
   by the Blueprint; the proxy key is shared server-side with the frontend.
3. Free instances do not provide the paid pre-deploy migration command. Prepare
   a private, untracked `.env.demo` using deploy/production.env.example and the
   actual demo settings, including `RUN_HISTORY_WORKER=false`. From repository
   root, apply migrations explicitly to the intended demo database:

   ```sh
   docker run --rm --env-file .env.demo \
     trust-api:local python -m scripts.migrate_production
   ```

   Confirm the database target and back up valued data first. Repeat this step
   for later schema changes; never run migrations inside the Docker build.
4. Use the allocated frontend domain for backend `FRONTEND_BASE_URL` and
   `CORS_ORIGINS`. Use the backend's actual public HTTPS URL for frontend
   `API_PROXY_ORIGIN`. Free web services cannot receive private-network traffic;
   do not use `API_PROXY_HOSTPORT` or the backend's internal hostname.
5. Redeploy backend, then frontend. Check backend `/api/v1/health/ready`, frontend
   `/health`, and real email sign-in, text history, credential and share/revoke
   journeys. Review ingress/IP configuration as in production_deployment.md.
   For demos, open backend readiness and allow it to wake before opening the
   frontend: an idle backend can take longer than the proxy's request timeout.

## What is available

Existing database-backed text journeys and static page language dictionaries are
retained. SMS verification is disabled until a real provider is configured.
Identity/payment stand-ins remain blocked; no qualifying review evidence is
fabricated. Existing provider and evidence dependencies still apply.

`RUN_HISTORY_WORKER`, `HISTORY_AI_ENABLED` and `HISTORY_SPEECH_ENABLED` are false.
There is no durable audio storage, transcription, AI draft generation, machine
message translation or spoken playback in this profile. Do not enable them on
ephemeral storage. Full voice requires durable private storage and reliable
processing plus validated providers; the current free profile does not supply it.

## Limits and cost

Render free web services sleep after 15 minutes without inbound traffic, lose
local files on restart and share 750 running hours per workspace per month.
Two constantly running web services exceed this shared allocation. Do not use
keep-alive tricks; this profile is for intermittent demos. Free Redis loses
its data on restart, including temporary rate-limit counters. Persistent trust
records remain in PostgreSQL. Build, bandwidth, database and external-provider
quotas apply; configuring free hosting does not make SMS, speech, model compute
or domain purchases free. Monitor usage and disable automatic paid upgrades.

Sources: [Render free limits](https://render.com/docs/free),
[Blueprint Path](https://render.com/docs/infrastructure-as-code),
[free pre-deploy limitation](https://render.com/docs/deploy-rails-6-7),
[Neon free plan](https://neon.com/blog/neon-free-plan-1-gb-per-project).

Local validation covers YAML and the free-service invariants. Render dashboard
validation and a deployed end-to-end demo remain operator checks. No services,
accounts or databases were created by preparing these files.
