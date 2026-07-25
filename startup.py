"""Start backend and frontend development servers."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parent
LOG_DIR = ROOT / "logs"
BACKEND_PORT = "8109"
FRONTEND_PORT = "5178"


def backend_python() -> str:
    candidates = [
        ROOT / "backend" / ".venv" / "Scripts" / "python.exe",
        ROOT / "backend" / ".venv" / "bin" / "python",
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return sys.executable


def npm_command() -> str:
    npm = shutil.which("npm.cmd") or shutil.which("npm")
    if not npm and sys.platform == "win32":
        program_files = Path(os.environ.get("ProgramFiles", "C:/Program Files"))
        candidate = program_files / "nodejs" / "npm.cmd"
        if candidate.exists():
            npm = str(candidate)
    if not npm:
        raise RuntimeError("npm was not found in PATH. Install Node.js/npm before starting the frontend.")
    return npm


def start_process(name: str, args: list[str], log_file: Path) -> subprocess.Popen:
    log = log_file.open("w", encoding="utf-8")
    process = subprocess.Popen(
        args,
        cwd=ROOT,
        stdout=log,
        stderr=subprocess.STDOUT,
        creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
    )
    print(f"{name} PID={process.pid}", flush=True)
    return process


def main() -> int:
    LOG_DIR.mkdir(exist_ok=True)

    backend = start_process(
        "Backend",
        [
            backend_python(),
            "-m",
            "uvicorn",
            "app.main:create_app",
            "--factory",
            "--host",
            "127.0.0.1",
            "--port",
            BACKEND_PORT,
            "--app-dir",
            "backend",
        ],
        LOG_DIR / "backend.log",
    )
    time.sleep(2)

    frontend = start_process(
        "Frontend",
        [
            npm_command(),
            "--prefix",
            "frontend",
            "run",
            "dev",
            "--",
            "--host",
            "127.0.0.1",
            "--port",
            FRONTEND_PORT,
        ],
        LOG_DIR / "frontend.log",
    )

    print(f"Backend:  http://127.0.0.1:{BACKEND_PORT}", flush=True)
    print(f"Frontend: http://127.0.0.1:{FRONTEND_PORT}", flush=True)
    print("Press Ctrl+C to stop.", flush=True)

    try:
        while True:
            time.sleep(2)
            if backend.poll() is not None:
                print("Backend exited. See logs/backend.log.", flush=True)
                return backend.returncode or 1
            if frontend.poll() is not None:
                print("Frontend exited. See logs/frontend.log.", flush=True)
                return frontend.returncode or 1
    except KeyboardInterrupt:
        backend.terminate()
        frontend.terminate()
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
