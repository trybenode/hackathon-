"""Run private evidence retention cleanup from an operator scheduler; never changes scores."""

import asyncio
from app.db.session import async_session_factory
from app.services.ownership_imports import expire, expire_orphans


async def main() -> None:
    async with async_session_factory() as session:
        await expire(session)
        await session.commit()
        await expire_orphans(session)


if __name__ == "__main__":
    asyncio.run(main())
