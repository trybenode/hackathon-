# Dynamic Trust Infrastructure

A trust API and platform-independent worker verification MVP.

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

Copy `.env.example` to `.env` and set the shared Neon `DATABASE_URL`. Do not commit `.env` or real credentials.

The runtime database is hosted on Neon so the team shares one database environment. Redis runs locally through Docker for development caching and rate limiting.

## Start local services

```bash
docker compose up -d redis
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
