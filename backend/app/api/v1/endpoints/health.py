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
