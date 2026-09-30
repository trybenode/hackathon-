"""Purpose: Seed a worker and job for manual API testing.

Dependencies: SQLAlchemy async engine and app.models.
Used by: local development.

Usage:
    cd backend
    .venv/bin/python scripts/seed_dev.py

Targets whatever DATABASE_URL resolves to, which locally is the Postgres in
.env.local. Run `alembic upgrade head` first: the schema comes from migrations,
not from this script.

Prints the worker and job ids to use when creating guarantor instruments.
"""

import asyncio
import sys
from decimal import Decimal
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.models.domain import (  # noqa: E402
    Job,
    JobType,
    Organization,
    OrganizationType,
    User,
    Worker,
)

DB_URL = get_settings().async_database_url


async def main() -> None:
    engine = create_async_engine(DB_URL)
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
