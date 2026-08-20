#!/usr/bin/env bash
# Shree Stay Homes & PG — Billing & Invoice Generator
# One-command local run for Linux: starts FastAPI backend (port 8001) + React frontend (port 3000).
# All invoice/tenant data stays in the browser's IndexedDB on this machine. No public hosting needed.
set -e

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
echo "==> Project root: $ROOT"

# --- env files (created from templates on first run) ---
if [ ! -f "$ROOT/backend/.env" ]; then
  cp "$ROOT/backend/.env.example" "$ROOT/backend/.env"
  echo "==> Created backend/.env from template"
fi
if [ ! -f "$ROOT/frontend/.env" ]; then
  cp "$ROOT/frontend/.env.example" "$ROOT/frontend/.env"
  echo "==> Created frontend/.env from template (backend URL: http://localhost:8001)"
fi

# --- backend ---
echo "==> Setting up backend (Python venv + dependencies)…"
cd "$ROOT/backend"
if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
pip install -q -r requirements.txt

echo "==> Starting API on http://localhost:8001 …"
uvicorn server:app --host 0.0.0.0 --port 8001 &
BACK_PID=$!
trap 'kill $BACK_PID 2>/dev/null || true' EXIT

# --- frontend ---
echo "==> Setting up frontend (this can take a few minutes on first run)…"
cd "$ROOT/frontend"
if [ ! -d node_modules ]; then
  if command -v yarn >/dev/null 2>&1; then
    yarn install
  else
    npm install
  fi
fi

echo ""
echo "==============================================================="
echo "  Shree Stay Homes & PG is starting…"
echo "  Open:  http://localhost:3000"
echo "  API:   http://localhost:8001/api"
echo "  Stop:  Ctrl+C"
echo "==============================================================="
echo ""

if command -v yarn >/dev/null 2>&1; then
  yarn start
else
  npm start
fi
