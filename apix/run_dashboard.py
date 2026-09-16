"""Start APIx's FastAPI service and Streamlit dashboard as one local app."""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parent
API_HEALTH_URL = "http://127.0.0.1:8001/api/v1/health"
API_COMMAND = [
    sys.executable, "-m", "uvicorn", "api.main:app", "--host", "127.0.0.1", "--port", "8001",
]
DASHBOARD_COMMAND = [sys.executable, "-m", "streamlit", "run", "dashboard/app.py"]


def api_is_ready() -> bool:
    try:
        with urlopen(API_HEALTH_URL, timeout=1) as response:
            return response.status == 200
    except (OSError, URLError):
        return False


def wait_for_api(process: subprocess.Popen[bytes] | None, timeout: float = 20) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if api_is_ready():
            return
        if process is not None and process.poll() is not None:
            raise RuntimeError(f"FastAPI exited during startup (exit code {process.returncode}).")
        time.sleep(0.25)
    raise RuntimeError("FastAPI did not become ready within 20 seconds.")


def main() -> int:
    started_api = False
    api_process: subprocess.Popen[bytes] | None = None
    try:
        if not api_is_ready():
            print("Starting FastAPI on http://127.0.0.1:8001 …")
            api_process = subprocess.Popen(API_COMMAND, cwd=ROOT)
            started_api = True
            wait_for_api(api_process)
        print("FastAPI is ready. Starting Streamlit …")
        return subprocess.call(DASHBOARD_COMMAND, cwd=ROOT)
    except RuntimeError as exc:
        print(f"Could not start APIx: {exc}", file=sys.stderr)
        return 1
    finally:
        if started_api and api_process is not None and api_process.poll() is None:
            api_process.terminate()
            try:
                api_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                api_process.kill()


if __name__ == "__main__":
    raise SystemExit(main())