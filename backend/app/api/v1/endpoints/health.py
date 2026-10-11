"""Purpose: Expose the API and Neon database readiness endpoint.

Dependencies: FastAPI, SQLAlchemy text queries, and app.db.session.
Used by: deployment probes and local smoke tests.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session

router = APIRouter(tags=["health"])


@router.get("/health", summary="Check API and database availability")
async def health_check(
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, str]:
    try:
        await session.execute(text("SELECT 1"))
    except SQLAlchemyError as error:
        raise HTTPException(status_code=503, detail="Database unavailable") from error

    return {"status": "ok", "service": "trust-infrastructure-api", "database": "ok"}


@router.get('/health/live', summary='Check API process liveness')
async def liveness() -> dict[str, str]:
    """Check the process without tying restarts to dependency availability."""
    return {'status': 'ok'}


@router.get('/health/ready', summary='Check database, limiter and configured worker readiness')
async def readiness(session: AsyncSession = Depends(get_db_session)) -> dict[str, str]:
    """Bound dependency probes; report no URLs, credentials or provider payloads."""
    import asyncio
    import time
    from pathlib import Path
    from redis.asyncio import Redis
    from redis.exceptions import RedisError
    from app.core.config import get_settings
    cfg = get_settings()
    try:
        await asyncio.wait_for(session.execute(text('SELECT 1')), timeout=3)
        async with Redis.from_url(cfg.redis_url, socket_connect_timeout=2, socket_timeout=2) as client:
            await asyncio.wait_for(client.ping(), timeout=3)
        if cfg.run_history_worker:
            heartbeat = Path(cfg.history_worker_heartbeat)
            if time.time() - heartbeat.stat().st_mtime > 180:
                raise OSError('Worker heartbeat stale')
    except (SQLAlchemyError, RedisError, OSError, TimeoutError) as error:
        raise HTTPException(status_code=503, detail='Required service unavailable') from error
    return {'status': 'ready'}
