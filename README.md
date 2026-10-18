# Dynamic Trust Infrastructure

A B2B trust API and platform-independent worker verification MVP.

## Product scope

The Platform API has three primary purposes:

1. **Onboarding trust assessment**: decide whether a worker can start offering a service, with a decision, confidence, trust band, optional guarantor, credential import, and normalized history.
2. **Continuous monitoring and risk flagging**: expose current standing, active flags, investigations, malicious/high-risk states, status history, and updates when new negative outcomes appear.
3. **Portable credentials**: export verified work history and trust records, then import them when a worker joins another platform.

Data normalization, configurable trust policies, outcome ingestion, guarantors, and audit trails support these three API purposes. Escrow and micro-insurance remain restricted to platform-independent jobs.

## Repository layout

- `backend/` FastAPI, SQLAlchemy, Alembic, and backend tests
- `frontend/` Next.js App Router application
- `docs/` architecture and setup notes
- `docker-compose.yml` local Redis only
- `AGENT.md` project rules and domain constraints

## Prerequisites

- Python 3.12+
- Node.js 20+
- pnpm
- Docker Desktop
- A shared Neon PostgreSQL database

## Configuration

[github.com/trybenode/hackathon-.git](https://github.com/trybenode/hackathon-.git)

**cd** hackathon-

git checkout -b feature/featureName

git add .
git commit -m "Add product scanning feature"
git push -u origin feature/product-scanner

#### **Branch Naming**

feature/trust-query-endpoint
feature/guarantor-sign-flow
fix/completion-auto-release
chore/add-ruff-config
docs/update-api-examples
hotfix/escrow-status-bug

**Rules**

* Branch from main
* Keep branches small and focused (ideally < 5 days of work)
* Delete the branch after merge
* Never commit directly to main
* 

**PR rules Required for every change:**

* Create a Pull Request into main
* Fill in a short description (what + why)
* Link related issue/task if one exists
* Ensure CI is green before merge
* At least **1 approval** from another team member
* Prefer squash merge (keeps main history clean)

PR Checklist

## What

## Why

## How to Test

## Checklist

- [ ] Follows naming conventions and AGENT.md rules
- [ ] Types are complete
- [ ] No secrets committed
- [ ] Critical demo path still works
- [ ] Tests added/updated for business logic
- [ ] Documentation updated if API contract changed

Copy `.env.example` to `.env` and set the shared Neon `DATABASE_URL`. Do not commit `.env` or real credentials.
Before enabling endpoints: set PLATFORM_API_KEY and CREDENTIAL_SIGNING_SECRET in .env (each at least 32 characters; generate with openssl rand -hex 32)

The runtime database is hosted on Neon so the team shares one database environment. Redis runs locally through Docker for development caching and rate limiting.

## Start local services

```bash
docker compose up -d redis
```
## db upgrade
```bash
PYTHONPATH=backend alembic -c alembic.ini upgrade head --sql
``` 

## Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

The API health endpoint is `GET http://localhost:8000/api/v1/health`.

## Frontend

```bash
cd frontend
pnpm install
pnpm dev
```

The web app is available at `http://localhost:3000`.

## Team database workflow

Alembic migrations target the shared Neon database through `DATABASE_URL`. Coordinate migration changes, review them before applying, and never put credentials in source control.


## Additional verification and ownership-reviewed imports

The optional pilot separates onboarding permissions from verified trust scoring.
Unsigned CSV + supporting PDF/image uploads require operations ownership review;
they contribute only to a separate provisional rating capped at 0.65. Building
History workers need genuine identity/liveness checks and human review. First-party
limited access enforces one active job, NGN25,000 per job and a 30-day approval.

Both flags default off. Start with the [setup, API examples and release checklist](docs/additional-verification.md).
Worker screen: `/worker/profile/record/verification`. Explicit-role reviewer queues:
`/review` and `/developer/reviews`. Authentication and normalization are unchanged.
