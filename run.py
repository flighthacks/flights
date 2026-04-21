#!/usr/bin/env python3
"""
Autofare — One-command launcher.

    python run.py

Starts the FastAPI backend on :8000 and Next.js frontend on :3000.
Open http://localhost:3000 in your browser.
"""

import os
import socket
import subprocess
import signal
import sys
import shutil
import time

ROOT = os.path.dirname(os.path.abspath(__file__))
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


def port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


def install_python_deps():
    reqs = os.path.join(ROOT, "requirements.txt")
    try:
        import fastapi, uvicorn, aiosqlite, yaml  # noqa: F401
    except ImportError:
        print("[*] Installing Python dependencies...")
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "-q", "-r", reqs],
            stdout=subprocess.DEVNULL,
        )


def install_node_deps():
    node_modules = os.path.join(FRONTEND_DIR, "node_modules")
    if not os.path.isdir(node_modules):
        print("[*] Installing frontend dependencies (npm install)...")
        subprocess.check_call(
            ["npm", "install", "--no-audit", "--no-fund"],
            cwd=FRONTEND_DIR,
            stdout=subprocess.DEVNULL,
        )


def main():
    print("=" * 50)
    print("  Autofare — Flight Search Optimizer")
    print("=" * 50)
    print()

    # ── Check ports ──
    if port_in_use(8000):
        print("[!] ERROR: Port 8000 already in use. Kill the process and retry.")
        sys.exit(1)

    has_node = bool(shutil.which("node") and shutil.which("npm"))
    if has_node and port_in_use(3000):
        print("[!] ERROR: Port 3000 already in use. Kill the process and retry.")
        sys.exit(1)

    # ── Install deps ──
    install_python_deps()
    if has_node:
        install_node_deps()

    # ── Check optional env vars ──
    if not os.environ.get("ANTHROPIC_API_KEY") and not os.environ.get("OPENAI_API_KEY"):
        print("[i] No LLM API key set — searches will use built-in strategies only.")
        print("    Set ANTHROPIC_API_KEY for AI-powered route proposals.\n")

    # ── Start backend ──
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

    # ── Start frontend ──
    if has_node:
        print("[*] Starting frontend on http://localhost:3000 ...")
        frontend = subprocess.Popen(
            ["npx", "next", "dev", "--port", "3000"],
            cwd=FRONTEND_DIR,
        )
        procs.append(frontend)
    else:
        print("[!] Node.js not found — skipping frontend.")
        print("    Install Node.js (https://nodejs.org) then re-run.")

    print()
    print("=" * 50)
    print("  Backend:  http://localhost:8000")
    print("  API docs: http://localhost:8000/docs")
    if has_node:
        print("  Frontend: http://localhost:3000  <-- open this")
    print()
    print("  Press Ctrl+C to stop.")
    print("=" * 50)

    # ── Wait ──
    try:
        while True:
            for p in procs:
                ret = p.poll()
                if ret is not None:
                    print(f"\n[!] A server exited (code {ret}). Shutting down.")
                    cleanup()
            time.sleep(1)
    except KeyboardInterrupt:
        cleanup()


if __name__ == "__main__":
    main()
