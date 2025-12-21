#!/usr/bin/env bash
set -euo pipefail
# backend/run.sh - wrapper to start the FastAPI app (uvicorn) and load .env
cd "$(dirname "$0")"

# load simple KEY=VALUE .env lines (ignore comments)
if [ -f .env ]; then
  export $(grep -v '^#' .env | xargs || true)
fi

# activate a venv if present (project root or backend/.venv)
if [ -f ../.venv/bin/activate ]; then
  # shellcheck source=/dev/null
  source ../.venv/bin/activate
elif [ -f .venv/bin/activate ]; then
  # shellcheck source=/dev/null
  source .venv/bin/activate
fi

exec python3 -m uvicorn main:app --host 0.0.0.0 --port 8000
