"""Secret-safe deployment preflight; validates configuration and optionally probes infrastructure/schema."""
import argparse
import asyncio
import tempfile
from pathlib import Path
from alembic.config import Config
from alembic.script import ScriptDirectory
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool
from app.core.config import get_settings
from app.core.production import validate_production_settings


async def dependencies() -> None:
    """Check schema head, Redis and private disk without mutating business records."""
    cfg = get_settings()
    engine = create_async_engine(cfg.async_database_url, poolclass=NullPool)
    try:
        async with engine.connect() as connection:
            current = set((await connection.execute(text('SELECT version_num FROM alembic_version'))).scalars())
        expected = set(ScriptDirectory.from_config(Config('alembic.ini')).get_heads())
        if current != expected:
            raise RuntimeError('Database is not at the application migration head.')
        async with Redis.from_url(cfg.redis_url, socket_connect_timeout=3, socket_timeout=3) as client:
            await client.ping()
        if cfg.run_history_worker:
            root = Path(cfg.history_audio_dir)
            root.mkdir(parents=True, exist_ok=True, mode=0o700)
            with tempfile.TemporaryFile(dir=root) as stream:
                stream.write(b'')
    finally:
        await engine.dispose()


def main() -> int:
    """Print only field names and generic failure states, never environment values."""
    parser = argparse.ArgumentParser()
    parser.add_argument('--online', action='store_true', help='Also check PostgreSQL schema, Redis and disk access.')
    args = parser.parse_args()
    cfg = get_settings()
    if cfg.environment == 'development':
        print('Set ENVIRONMENT=staging or production before running production preflight.')
        return 1
    try:
        validate_production_settings(cfg)
    except RuntimeError as error:
        print(str(error))
        return 1
    if args.online:
        try:
            asyncio.run(asyncio.wait_for(dependencies(), timeout=20))
        except Exception:
            print('Infrastructure preflight failed: check migration head, database, Redis and disk access.')
            return 1
    print('Production configuration validated' + ('; infrastructure/schema checks passed.' if args.online else '.'))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
