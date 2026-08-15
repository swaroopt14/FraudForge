#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="${ROOT}/backend${PYTHONPATH:+:$PYTHONPATH}"
python scripts/bootstrap_deploy.py
exec uvicorn backend.app:app --host "${HOST:-0.0.0.0}" --port "${API_PORT:-${PORT:-8000}}"
