"""Start local development services and stop child process groups together."""
import argparse
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import sys
import time


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--voice-worker", action="store_true", help="Also run the durable voice-processing worker (provider setup required).")
    args = parser.parse_args()
    python = ROOT / "backend/.venv/bin/python"
    for tool in ("docker", "pnpm"):
        if not shutil.which(tool):
            print(f"Install {tool} before starting development.", file=sys.stderr)
            return 1
    if not python.exists() or not (ROOT / "frontend/node_modules").exists():
        print("Install backend dependencies in backend/.venv and run pnpm install in frontend first.", file=sys.stderr)
        return 1
    for port in (8000, 3000):
        with socket.socket() as probe:
            try:
                probe.bind(("127.0.0.1", port))
            except OSError:
                print(f"Port {port} is occupied. Stop the existing dev server first.", file=sys.stderr)
                return 1
    try:
        subprocess.run(["docker", "compose", "up", "-d", "--wait", "redis"], cwd=ROOT, check=True)
    except subprocess.CalledProcessError:
        print("Redis startup failed. Make sure Docker Desktop is running.", file=sys.stderr)
        return 1
    commands = [
        (ROOT / "backend", [str(python), "-m", "uvicorn", "app.main:app", "--reload", "--port", "8000"]),
        (ROOT / "frontend", ["pnpm", "dev", "--port", "3000"]),
    ]
    if args.voice_worker:
        commands.append((ROOT / "backend", [str(python), "-m", "scripts.history_worker"]))
    children: list[subprocess.Popen] = []

    def stop(signum: int, frame: object) -> None:
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, stop)
    try:
        for cwd, command in commands:
            children.append(subprocess.Popen(command, cwd=cwd, start_new_session=True))
        print("\nFrontend: http://localhost:3000\nAPI docs: http://localhost:8000/docs\nCtrl+C stops application processes; Redis stays running.\n", flush=True)
        while True:
            for child in children:
                code = child.poll()
                if code is not None:
                    print("A development process exited; stopping the remaining processes.", file=sys.stderr)
                    return code or 1
            time.sleep(0.5)
    except KeyboardInterrupt:
        return 0
    finally:
        for child in children:
            if child.poll() is None:
                os.killpg(child.pid, signal.SIGTERM)
        deadline = time.monotonic() + 5
        for child in children:
            try:
                child.wait(timeout=max(0.1, deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL)
                child.wait()


if __name__ == "__main__":
    sys.exit(main())
