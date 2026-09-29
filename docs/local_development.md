# Local development and database parity

The deployed database is Postgres (Neon). Local work can use SQLite for speed,
but SQLite is not a substitute for Postgres when it comes to migrations.

## Two local setups

| | SQLite | Local Postgres |
| --- | --- | --- |
| Speed | fast (~5s suite) | slower (~22s suite) |
| Schema built by | `Base.metadata.create_all` | Alembic migrations |
| Catches migration bugs | **no** | yes |
| Enum handling | plain text | real enum types |

SQLite builds the schema straight from the models, so the migration files are
never executed. A migration can be wrong while every test passes — this is not
hypothetical: an early version of `b7c41d9e2a08` added lower-case
`agreement_status` labels while SQLAlchemy stores this enum by member *name*
(`ACTIVE`, `DRAFT`). Every SQLite test passed; the first Postgres insert would
have failed.

## Day to day (SQLite)

```bash
cd backend
.venv/bin/python scripts/seed_dev.py          # prints DATABASE_URL and WORKER_ID
DATABASE_URL=<printed url> .venv/bin/uvicorn app.main:app --port 8000
.venv/bin/pytest
```

## Before opening a PR (Postgres)

```bash
brew install postgresql@16 && brew services start postgresql@16
export PATH="/usr/local/opt/postgresql@16/bin:$PATH"

createdb trust_dev
cd backend
DATABASE_URL="postgresql+asyncpg://$(whoami)@localhost:5432/trust_dev" .venv/bin/alembic upgrade head

createdb trust_test
TEST_DATABASE_URL="postgresql+asyncpg://$(whoami)@localhost:5432/trust_test" .venv/bin/pytest
```

The first command proves the migrations apply from scratch; the second runs the
whole suite against Postgres semantics.

## Moving to Neon

With the above green, switching is only a URL change: point `DATABASE_URL` at
Neon, run `alembic upgrade head`, and seed if the database is empty.

## Rules that keep the two in step

- Every schema change ships as a migration. Never model-only.
- Enum labels are the member **name** (upper-case), matching SQLAlchemy's default.
- Additive changes where possible: Postgres cannot drop an enum label.
- No SQLite-specific assumptions in application code.
