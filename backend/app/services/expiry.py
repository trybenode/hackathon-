"""Purpose: Expire guarantor instruments whose validity period has ended, and
remind clients who have not confirmed a completed job. No money moves here.

Dependencies: SQLAlchemy async sessions, app.services.guarantor and app.services.escrow.
Used by: the background sweep started with the app, and the ops endpoint.

Expiry is time-based, so nothing in a request path can cause it. Without a
sweep an instrument stays Active past `valid_until`, which the lifecycle in
the SRS (FR-4.4) says should not happen.
"""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy.ext.asyncio import async_sessionmaker

from app.services.escrow import remind_unconfirmed
from app.services.guarantor import expire_due_instruments

logger = logging.getLogger(__name__)


async def run_sweep(session_factory: async_sessionmaker) -> int:
    """Expire everything that is due, and report how many."""

    async with session_factory() as session:
        expired = await expire_due_instruments(session)
        await session.commit()

    if expired:
        logger.info("Expired %d guarantor instrument(s)", len(expired))

    # Separate session: an email hiccup must not undo expiry.
    async with session_factory() as session:
        reminded = await remind_unconfirmed(session)
        await session.commit()

    if reminded:
        logger.info("Reminded %d client(s) to confirm a completed job", len(reminded))

    return len(expired)


async def sweep_forever(session_factory: async_sessionmaker, interval_seconds: int) -> None:
    """Run the sweep on a loop until cancelled.

    A failed sweep is logged and retried on the next tick rather than killing
    the loop: a transient database error should not stop expiry for the life
    of the process.
    """

    while True:
        try:
            await run_sweep(session_factory)
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 - the loop must outlive one bad run
            logger.exception("Expiry sweep failed; retrying next interval")

        await asyncio.sleep(interval_seconds)
