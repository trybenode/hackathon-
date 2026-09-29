"""Purpose: Create a local SQLite database with one worker for manual API testing.

Dependencies: SQLAlchemy async engine with aiosqlite and app.models.
Used by: developers running the API locally without Postgres/Neon.

Usage:
    cd backend
    .venv/bin/python scripts/seed_dev.py

Prints the worker id to use when creating guarantor instruments.
"""

import asyncio
import os
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

from app.db.base import Base  # noqa: E402
from app.models.domain import User, Worker  # noqa: E402

DB_PATH = BACKEND_ROOT / "local_dev.db"
# Defaults to a local SQLite file; set DATABASE_URL to seed Postgres or Neon.
# The absolute path keeps the URL valid through the rewrite in core.config.
DB_URL = os.environ.get("DATABASE_URL") or f"sqlite+aiosqlite:///{DB_PATH}"


async def main() -> None:
    engine = create_async_engine(DB_URL)
    async with engine.begin() as connection:
        # Harmless on a migrated database: existing tables are left alone.
        await connection.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        user = User(email="worker@example.com", display_name="Jane A.")
        session.add(user)
        await session.flush()

        worker = Worker(user_id=user.id)
        session.add(worker)
        await session.commit()

        print(f"DATABASE_URL={DB_URL}")
        print(f"WORKER_ID={worker.id}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
