"""Purpose: Create a local SQLite database with one worker for manual API testing.

Dependencies: SQLAlchemy async engine with aiosqlite and app.models.
Used by: developers running the API locally without Postgres/Neon.

Usage:
    cd backend
    .venv/bin/python scripts/seed_dev.py                # create schema + demo rows
    .venv/bin/python scripts/seed_dev.py --schema-only   # create missing tables only

Prints the worker and job ids to use when creating guarantor instruments.

The local SQLite database is built by create_all rather than migrations, so
run this with --schema-only after pulling a change that adds a table.
"""

import asyncio
import os
import sys
from decimal import Decimal
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

from app.db.base import Base  # noqa: E402
from app.models.domain import (  # noqa: E402
    Job,
    JobType,
    Organization,
    OrganizationType,
    User,
    Worker,
)

DB_PATH = BACKEND_ROOT / "local_dev.db"
# Defaults to a local SQLite file; set DATABASE_URL to seed Postgres or Neon.
# The absolute path keeps the URL valid through the rewrite in core.config.
DB_URL = os.environ.get("DATABASE_URL") or f"sqlite+aiosqlite:///{DB_PATH}"


async def main() -> None:
    schema_only = "--schema-only" in sys.argv

    engine = create_async_engine(DB_URL)
    async with engine.begin() as connection:
        # Harmless on a migrated database: existing tables are left alone.
        await connection.run_sync(Base.metadata.create_all)

    if schema_only:
        print(f"DATABASE_URL={DB_URL}")
        print("Schema is up to date.")
        await engine.dispose()
        return

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        user = User(email="worker@example.com", display_name="Jane A.")
        session.add(user)
        await session.flush()

        worker = Worker(
            user_id=user.id,
            role="Cleaner",
            location="Lekki, Lagos",
        )
        organization = Organization(
            name="Sparkle Homes",
            organization_type=OrganizationType.EMPLOYER,
        )
        session.add_all([worker, organization])
        await session.flush()

        job = Job(
            worker_id=worker.id,
            organization_id=organization.id,
            job_type=JobType.INDEPENDENT,
            title="Home cleaning",
            agreed_amount=Decimal("25000.00"),
        )
        session.add(job)
        await session.commit()

        print(f"DATABASE_URL={DB_URL}")
        print(f"WORKER_ID={worker.id}")
        print(f"JOB_ID={job.id}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
