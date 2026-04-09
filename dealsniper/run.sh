#!/usr/bin/env bash
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"

echo "=== Deal Sniper Setup ==="

# ── Backend ──────────────────────────────────────────────────────────────────
echo ""
echo "[1/4] Installing backend dependencies..."
cd "$ROOT/backend"
pip install -r requirements.txt --quiet 2>/dev/null || pip install -r requirements.txt
pip install --no-deps flights 2>/dev/null || true

echo "[2/4] Starting backend on port 8000..."
uvicorn main:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

# Wait up to 15 seconds for backend to be ready
for i in $(seq 1 15); do
  if curl -s http://localhost:8000/api/health > /dev/null 2>&1; then
    echo "  Backend running (PID $BACKEND_PID)"
    break
  fi
  if [ "$i" -eq 15 ]; then
    echo "  ERROR: Backend failed to start after 15s. Check logs above."
    exit 1
  fi
  sleep 1
done

# ── Frontend ─────────────────────────────────────────────────────────────────
echo ""
echo "[3/4] Installing frontend dependencies..."
cd "$ROOT/frontend"
npm install --silent 2>/dev/null || npm install

echo "[4/4] Starting frontend on port 3001..."
echo ""
echo "========================================="
echo "  Deal Sniper is ready!"
echo "  Frontend: http://localhost:3001"
echo "  Backend:  http://localhost:8000"
echo "  API Docs: http://localhost:8000/docs"
echo "========================================="
echo ""

npx next dev --port 3001
