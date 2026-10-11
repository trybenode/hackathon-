"""Smoke-test the actual production supervisor against an explicitly disposable database; no provider calls."""
import argparse
import json
import os
from pathlib import Path
import secrets
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--database-url', required=True, help='Disposable migrated local PostgreSQL database only.')
    parser.add_argument('--redis-url', default='redis://localhost:6379/15')
    parser.add_argument('--serverless', action='store_true', help='Check the no-worker serverless demo profile.')
    args = parser.parse_args()
    if not args.database_url.startswith('postgresql+asyncpg://') or '@localhost:' not in args.database_url:
        raise SystemExit('This local smoke test requires an explicit disposable localhost database.')
    backend = Path(__file__).resolve().parents[1] / 'backend'
    python = sys.executable
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0)); port = probe.getsockname()[1]
    with tempfile.TemporaryDirectory(prefix='trust-production-smoke-') as private:
        env = {**os.environ, 'ENVIRONMENT':'production', 'DATABASE_URL':args.database_url,
               'REDIS_URL':args.redis_url, 'PORT':str(port),
               'CREDENTIAL_SIGNING_SECRET':secrets.token_hex(32), 'INTERNAL_PROXY_SECRET':secrets.token_hex(32),
               'RESEND_API_KEY':'smoke-no-email-sent', 'RESEND_FROM':'Trust <login@example.com>',
               'FRONTEND_BASE_URL':'https://app.example.com', 'CORS_ORIGINS':'https://app.example.com',
               'SMS_PROVIDER':'disabled', 'RUN_HISTORY_WORKER':'true', 'HISTORY_AUDIO_DIR':private,
               'HISTORY_WORKER_HEARTBEAT':str(Path(private)/'heartbeat'), 'HISTORY_AI_ENABLED':'false',
               'HISTORY_SPEECH_ENABLED':'false', 'PAYSCROW_API_KEY':'', 'PLATFORM_API_KEY':''}
        env['DEPLOYMENT_MODE'] = 'serverless' if args.serverless else 'container'
        if args.serverless:
            env.update(RUN_HISTORY_WORKER='false', EXPIRY_SWEEP_SECONDS='0')
        with tempfile.TemporaryFile() as log:
            process = subprocess.Popen([str(python), '-m', 'scripts.start_production'], cwd=backend, env=env, stdout=log, stderr=log)
            try:
                ready = False
                for _ in range(100):
                    if process.poll() is not None: break
                    try:
                        with urllib.request.urlopen(f'http://127.0.0.1:{port}/api/v1/health/ready', timeout=1) as response:
                            ready = json.load(response)['status'] == 'ready'
                        if ready: break
                    except (OSError, ValueError): pass
                    time.sleep(0.1)
                assert ready, 'API/worker did not become ready.'
                checked = subprocess.run([str(python), '-m', 'scripts.check_production', '--online'], cwd=backend, env=env, capture_output=True)
                assert checked.returncode == 0, 'Online production preflight failed.'
                if args.serverless:
                    children = subprocess.check_output(['pgrep', '-P', str(process.pid)], text=True).split()
                    assert len(children) == 1, 'Serverless profile started a worker.'
                    print('Serverless runtime smoke passed: API readiness, online preflight and no worker process.')
                    return
                # Kill only our own worker child to prove fail-together supervision.
                children = subprocess.check_output(['pgrep', '-P', str(process.pid)], text=True).split()
                worker = next(int(pid) for pid in children if 'scripts.history_worker' in subprocess.check_output(['ps', '-p', pid, '-o', 'command='], text=True))
                os.kill(worker, signal.SIGTERM)
                assert process.wait(timeout=15) != 0, 'Supervisor did not fail when the worker exited.'
                print('Production runtime smoke passed: API/worker readiness, online preflight and fail-together supervision.')
            finally:
                if process.poll() is None:
                    process.terminate()
                    process.wait(timeout=30)


if __name__ == '__main__':
    main()
