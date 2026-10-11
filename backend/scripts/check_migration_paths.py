"""Check empty/previous-head upgrades in newly created disposable databases.

Uses TEST_DATABASE_URL for the PostgreSQL server and creates only temporary
integration_* databases. Requires CREATE DATABASE permission; never resets the
supplied database. Run before the suite in local Docker or CI.
"""
import asyncio
import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

BACKEND = Path(__file__).resolve().parents[1]
STARTS = (None, "1d7fe6fb9d97", "8f41c20a9e37", "a83c2d43e9f2", "f69a915488e3")


async def main() -> None:
    configured = os.environ.get("TEST_DATABASE_URL")
    if not configured:
        raise SystemExit("Set TEST_DATABASE_URL to a disposable local/CI PostgreSQL server.")
    url = make_url(configured)
    if not url.drivername.startswith("postgresql"):
        raise SystemExit("Migration-path checks require PostgreSQL.")
    url = url.set(drivername="postgresql+asyncpg")
    admin = create_async_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    try:
        for starting_head in STARTS:
            name = f"integration_{uuid4().hex}"
            async with admin.connect() as connection:
                await connection.execute(text(f'CREATE DATABASE "{name}"'))
            try:
                env = {**os.environ, "DATABASE_URL": url.set(database=name).render_as_string(hide_password=False)}
                if starting_head:
                    subprocess.run([sys.executable, "-m", "alembic", "upgrade", starting_head], cwd=BACKEND, env=env, check=True)
                subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=BACKEND, env=env, check=True)
                subprocess.run([sys.executable, "scripts/check_migrations.py"], cwd=BACKEND, env=env, check=True)
                print(f"Verified migration path: {starting_head or 'empty'} -> head", flush=True)
            finally:
                async with admin.connect() as connection:
                    await connection.execute(text(f'DROP DATABASE "{name}"'))
    finally:
        await admin.dispose()


if __name__ == "__main__":
    asyncio.run(main())
