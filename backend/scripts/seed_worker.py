"""Create or reuse a worker account without fabricating work or verification.

Run from backend: .venv/bin/python scripts/seed_worker.py
Uses the configured database; remote databases require --allow-remote.
"""
import argparse
import asyncio
from pathlib import Path
import sys
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from app.core.config import get_settings
from app.models.domain import User, Worker


async def seed(email: str, name: str, allow_remote: bool) -> None:
    """Idempotently seed an active user and worker in the selected dev database."""
    settings = get_settings()
    if settings.environment != "development":
        raise SystemExit("Worker seeding is restricted to development.")
    url = settings.async_database_url
    if urlsplit(url).hostname not in ("localhost", "127.0.0.1", "::1") and not allow_remote:
        raise SystemExit("Configured database is remote. Confirm the target before using --allow-remote.")
    engine = create_async_engine(url)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            async with session.begin():
                user = await session.scalar(select(User).where(User.email == email))
                if user is None:
                    user = User(email=email, display_name=name)
                    session.add(user)
                    await session.flush()
                elif not user.is_active:
                    raise SystemExit("Existing account is inactive; it was not modified.")
                worker = await session.scalar(select(Worker).where(Worker.user_id == user.id))
                if worker is None:
                    worker = Worker(user_id=user.id, role="Cleaner", location="Lagos")
                    session.add(worker)
                    await session.flush()
            print(f"Worker account ready: {user.email}")
            print(f"WORKER_ID={worker.id}")
            print("No jobs, ratings, identity checks or guarantees were created.")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", default="worker@example.com")
    parser.add_argument("--name", default="Demo Worker")
    parser.add_argument("--allow-remote", action="store_true")
    args = parser.parse_args()
    email = args.email.strip().lower()
    if "@" not in email or len(email) > 254:
        parser.error("Provide a valid account email.")
    asyncio.run(seed(email, args.name, args.allow_remote))
