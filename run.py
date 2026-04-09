#!/usr/bin/env python3
"""
Autofare — One-command launcher.

    python run.py

Starts the FastAPI backend on :8000 and Next.js frontend on :3000.
Open http://localhost:3000 in your browser.
"""

import os
import sys
import subprocess
import signal
import time
import shutil

ROOT = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.join(ROOT, "web", "backend")
FRONTEND_DIR = os.path.join(ROOT, "web", "frontend")

os.chdir(ROOT)
sys.path.insert(0, ROOT)

procs = []


def cleanup(*_):
    print("\nShutting down...")
    for p in procs:
        try:
            p.terminate()
        except Exception:
            pass
    sys.exit(0)


signal.signal(signal.SIGINT, cleanup)
signal.signal(signal.SIGTERM, cleanup)


def check_python_deps():
    missing = []
    for mod in ["fastapi", "uvicorn", "aiosqlite", "yaml"]:
        try:
            __import__(mod)
        except ImportError:
            missing.append(mod)
    if missing:
        print(f"[*] Installing Python dependencies...")
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", "-q",
            "fastapi", "uvicorn", "aiosqlite", "pyyaml",
            "selectolax", "primp", "protobuf", "typing_extensions",
        ])


def check_node_deps():
    node_modules = os.path.join(FRONTEND_DIR, "node_modules")
    if not os.path.isdir(node_modules):
        print("[*] Installing frontend dependencies (npm install)...")
        subprocess.check_call(["npm", "install"], cwd=FRONTEND_DIR)


def main():
    print("=" * 50)
    print("  Autofare — Flight Search Optimizer")
    print("=" * 50)

    # Check deps
    check_python_deps()

    has_node = shutil.which("node") and shutil.which("npm")
    if has_node:
        check_node_deps()

    # Start backend
    print("[*] Starting backend on http://localhost:8000 ...")
    env = os.environ.copy()
    env["PYTHONPATH"] = ROOT + os.pathsep + env.get("PYTHONPATH", "")
    backend = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "web.backend.app:app",
         "--host", "0.0.0.0", "--port", "8000", "--reload"],
        cwd=ROOT,
        env=env,
    )
    procs.append(backend)
    time.sleep(2)

    # Start frontend
    if has_node:
        print("[*] Starting frontend on http://localhost:3000 ...")
        frontend = subprocess.Popen(
            ["npx", "next", "dev", "--port", "3000"],
            cwd=FRONTEND_DIR,
        )
        procs.append(frontend)
    else:
        print("[!] Node.js not found — skipping frontend.")
        print("    Install Node.js and run: cd web/frontend && npm install && npm run dev")

    print()
    print("=" * 50)
    print("  Backend:  http://localhost:8000")
    print("  API docs: http://localhost:8000/docs")
    if has_node:
        print("  Frontend: http://localhost:3000  <-- open this")
    print()
    print("  Press Ctrl+C to stop.")
    print("=" * 50)

    # Wait for processes
    try:
        while True:
            for p in procs:
                if p.poll() is not None:
                    print(f"[!] Process exited with code {p.returncode}")
                    cleanup()
            time.sleep(1)
    except KeyboardInterrupt:
        cleanup()


if __name__ == "__main__":
    main()
