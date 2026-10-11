"""Supervise API and optional durable worker on one mounted disk; used by managed-container startup."""
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from app.core.config import get_settings
from app.core.production import validate_production_settings


def main() -> int:
    """Exit if either child fails; terminate both cleanly on platform shutdown."""
    cfg = get_settings()
    validate_production_settings(cfg)
    children: list[subprocess.Popen] = []
    stopping = False
    def stop(signum: int, frame: object) -> None:
        nonlocal stopping
        stopping = True
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        if cfg.run_history_worker:
            Path(cfg.history_worker_heartbeat).unlink(missing_ok=True)
            children.append(subprocess.Popen([sys.executable, '-m', 'scripts.history_worker']))
        children.append(subprocess.Popen([sys.executable, '-m', 'uvicorn', 'app.main:app', '--host', '0.0.0.0', '--port', os.environ.get('PORT', '8000'), '--workers', '1', '--no-proxy-headers', '--no-server-header']))
        while not stopping:
            for child in children:
                if child.poll() is not None:
                    return child.returncode or 1
            time.sleep(0.2)
        return 0
    finally:
        for child in children:
            if child.poll() is None:
                child.terminate()
        deadline = time.monotonic() + 25
        for child in children:
            try:
                child.wait(timeout=max(0.1, deadline-time.monotonic()))
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()


if __name__ == '__main__':
    raise SystemExit(main())
