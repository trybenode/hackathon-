# Local development

Local development runs against **Postgres**, the same engine as Neon, so
migrations and types behave exactly as they will in production.

## One-time setup

```bash
brew install postgresql@16 && brew services start postgresql@16
export PATH="/usr/local/opt/postgresql@16/bin:$PATH"
createdb trust_dev
```

Point the backend at it with a `.env.local` beside `.env` (gitignored, one per
machine — `.env` keeps the shared/Neon settings):

```
DATABASE_URL=postgresql+asyncpg://YOUR_USER@localhost:5432/trust_dev
```

`.env.local` wins over `.env`, so nothing in the shared file needs editing.

## Day to day

```bash
cd backend
.venv/bin/alembic upgrade head          # schema comes from migrations
.venv/bin/python scripts/seed_dev.py    # a worker, organisation and job
.venv/bin/python scripts/seed_guarantor.py you@example.com
.venv/bin/uvicorn app.main:app --port 8000 --reload
```

The seed scripts follow the same `DATABASE_URL` as the app, so they always
target whichever database the API is using.

## Tests

```bash
cd backend
.venv/bin/pytest                        # in-memory SQLite, fast

createdb trust_test
TEST_DATABASE_URL="postgresql+asyncpg://$(whoami)@localhost:5432/trust_test" .venv/bin/pytest
```

The default suite uses in-memory SQLite because it is quick (about 8s versus
22s), which keeps the coding loop tight.

**The Postgres run is not optional before merging — CI enforces it.**
`.github/workflows/ci.yml` applies the migrations to a real Postgres, checks
that they match the models, then runs the whole suite against it. Running the
commands above locally just means finding out before the PR rather than after.

To check migration drift yourself:

```bash
cd backend
.venv/bin/python scripts/check_migrations.py
```

## Why Postgres locally

SQLite built its schema from `create_all`, which meant:

- **Migrations never ran**, so a broken migration passed every test. An early
  version of `b7c41d9e2a08` added lower-case `agreement_status` labels while
  SQLAlchemy stores this enum by member *name* (`ACTIVE`, `DRAFT`). Every
  SQLite test passed; the first Postgres insert would have failed.
- **New columns never appeared** in an existing local database, because
  `create_all` adds missing tables but never alters existing ones. Adding a
  column meant deleting the database and reseeding.
- **Timestamps came back naive** where Postgres returns aware ones, which
  crashed the notifications endpoint on a sort.

With Postgres locally, `alembic upgrade head` handles all of this.

## Moving to Neon

Remove or edit `.env.local` so `DATABASE_URL` resolves to Neon, run
`alembic upgrade head`, and seed if the database is empty.

## Rules that keep environments in step

- Every schema change ships as a migration. Never model-only.
- Enum labels are the member **name** (upper-case), matching SQLAlchemy's default.
- Additive changes where possible: Postgres cannot drop an enum label.
