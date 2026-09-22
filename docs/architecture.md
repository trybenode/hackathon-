# Initial Architecture

## Runtime topology

```text
Next.js frontend :3000
        |
FastAPI backend :8000
     /       \
Neon         Redis :6379
PostgreSQL   local Docker service
(shared)
```

Neon PostgreSQL is the shared source of truth from the first scaffold. The local Compose stack intentionally contains Redis only. This keeps team members aligned on schema and migration behavior while retaining a disposable local cache and rate-limiting dependency.

## Boundaries

- API routes handle HTTP validation and dependency injection.
- Services own trust, normalization, credential, guarantor, job, and escrow business logic.
- SQLAlchemy models own persistence mapping.
- Pydantic schemas own request and response contracts.
- External identity and escrow providers remain integrations, not core domain models.

## Initial vertical slice

The first runnable slice is configuration plus `GET /api/v1/health`. Scoring, KYC, Vesti, credentials, and job workflows will be added behind the existing module boundaries.

## Database discipline

Use `DATABASE_URL` from the environment. Runtime connections should use SQLAlchemy's async PostgreSQL driver and Neon-compatible SSL settings. Alembic migrations are the shared schema contract and should be applied deliberately against the team Neon project.
