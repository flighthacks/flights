#!/bin/bash
# Autofare Development Server Launcher
#
# Starts both the FastAPI backend and Next.js frontend.
#
# Prerequisites:
#   pip install -r web/backend/requirements.txt
#   cd web/frontend && npm install
#
# Environment variables (optional):
#   JWT_SECRET           - JWT signing key (defaults to dev key)
#   STRIPE_SECRET_KEY    - Stripe secret key (required for billing)
#   ANTHROPIC_API_KEY    - Anthropic API key (required for LLM proposals)

set -e

DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=========================================="
echo "  Autofare Dev Server"
echo "=========================================="

# Start backend
echo "[*] Starting FastAPI backend on :8000..."
cd "$DIR/.."
uvicorn web.backend.app:app --reload --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

# Start frontend
echo "[*] Starting Next.js frontend on :3000..."
cd "$DIR/frontend"
npm run dev &
FRONTEND_PID=$!

echo ""
echo "  Backend:  http://localhost:8000"
echo "  Frontend: http://localhost:3000"
echo "  API docs: http://localhost:8000/docs"
echo ""
echo "  Press Ctrl+C to stop both servers."
echo "=========================================="

# Cleanup on exit
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null" EXIT
wait
