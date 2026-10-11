"""Run one coordinated Alembic upgrade using a PostgreSQL advisory lock; serves release jobs."""
import asyncio
import os
import sys
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool
from app.core.config import get_settings


async def main() -> int:
    """Serialize release migration jobs; never run automatically in API replicas."""
    cfg = get_settings()
    migration_url = cfg.migration_database_url or cfg.database_url
    engine = create_async_engine(cfg.model_copy(update={"database_url": migration_url}).async_database_url, poolclass=NullPool)
    try:
        async with engine.connect() as connection:
            # Deployment coordination lock, distinct from feature-level locks.
            await connection.execute(text('SET statement_timeout = 60000'))
            await connection.execute(text('SELECT pg_advisory_lock(783249102)'))
            try:
                process = await asyncio.create_subprocess_exec(sys.executable, '-m', 'alembic', 'upgrade', 'head', env={**os.environ, 'DATABASE_URL': migration_url})
                return await process.wait()
            finally:
                await connection.execute(text('SELECT pg_advisory_unlock(783249102)'))
    finally:
        await engine.dispose()


if __name__ == '__main__':
    raise SystemExit(asyncio.run(main()))
