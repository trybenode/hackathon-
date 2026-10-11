"""Run durable voice/speech jobs with a liveness heartbeat; used by the production supervisor and dev launcher."""
import asyncio
from contextlib import suppress
import logging
from pathlib import Path
from app.core.config import get_settings
from app.core.production import validate_production_settings
from app.db.session import async_session_factory
from app.services.history_drafts import process_one
from app.services.history_speech import process_one as process_speech


async def heartbeat_forever(path: Path) -> None:
    """Keep event-loop liveness visible even during long awaited provider requests."""
    while True:
        try:
            await asyncio.to_thread(path.touch, mode=0o600)
        except OSError:
            logging.getLogger(__name__).warning('History worker heartbeat unavailable.')
        await asyncio.sleep(10)


async def main() -> None:
    """Process leased jobs; preserve retries without logging customer/provider payloads."""
    cfg = get_settings()
    validate_production_settings(cfg)
    task = asyncio.create_task(heartbeat_forever(Path(cfg.history_worker_heartbeat)))
    try:
        while True:
            try:
                speech_worked = await process_speech(async_session_factory)
                worked = await process_one(async_session_factory) or speech_worked
            except Exception:
                logging.getLogger(__name__).warning('History processing iteration failed; will retry.')
                worked = False
            if not worked:
                await asyncio.sleep(2)
    finally:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task


if __name__ == '__main__':
    asyncio.run(main())
