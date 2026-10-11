# Free demo deployment plan

1. Story/acceptance: an operator can select a separate free Render Blueprint for
   text-based demos without provisioning paid services, a disk or model hosting.
2. Impact: add render.free.yaml and setup instructions; reuse both Docker images
   and existing disabled-provider flags. Preserve the paid production Blueprint.
3. Contracts: no API/auth/schema changes. Backend becomes a public HTTPS web
   service; frontend proxies to its public origin with the existing shared secret.
   Migrations are an explicit operator step because free pre-deploy jobs are absent.
4. Dependencies: isolated Neon free database, Render free Key Value, verified
   email configuration and actual allocated frontend/backend domains. Provider
   quotas, native review and production acceptance are not satisfied by free hosting.
5. Sequence: separate Blueprint, migration/domain instructions, local YAML and
   service compatibility checks, then operator-side Render validation and demo.
6. Verify: every service uses free, no disk/private-service/pre-deploy settings,
   processing flags disabled, public upstream configuration and secret references
   preserved. Check real sign-in/record/share flows after deployment.
7. Rollout: demo only; sleeping services, shared hour quotas and volatile Redis
   are expected. Preserve PostgreSQL data; select paid storage/worker setup before
   enabling voice or making production reliability claims. No cloud actions here.
