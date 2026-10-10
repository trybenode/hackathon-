Implemented:

* SQLAlchemy declarative base with naming conventions
* UUID primary keys
* UTC timestamps
* PostgreSQL enums
* Foreign keys and delete rules
* Validation constraints
* Core indexes and uniqueness rules
* Alembic metadata registration
* Neon-compatible Alembic connection
* Initial migration




## What

* Added `POST /api/v1/trust/query`, using stored verified history and shared `assess_worker()` scoring with cached assessment reuse.
* Added authenticated credential export/import using worker-bound, expiring HMAC-signed bundles.
* Added normalized outcome provenance fields and an Alembic migration.
* Prevented unknown client IDs from producing repeat-hire signals.

## Why

Provides a consistent onboarding decision for platforms and portable verified history for workers, while letting outcome ingestion reuse the same scoring logic.

## How to Test

* `cd /Users/user/IT/hackathon && pytest -q backend/tests` — **86 passed**
* `PYTHONPATH=backend alembic -c alembic.ini upgrade head --sql` — migration SQL renders offline; no database changes applied.

## Checklist

* [X] Follows naming conventions and `AGENT.md` rules
* [ ] Types are verified in the editor; Pylance currently cannot resolve SQLAlchemy in the selected interpreter
* [X] No secrets committed
* [ ] Critical path verified against Neon; the migration is not applied, and Neon is behind the repository’s migration head
* [X] Tests added/updated for business logic
* [X] Documentation updated for the API contract and required environment variables
