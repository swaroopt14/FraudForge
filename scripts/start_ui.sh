#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="${ROOT}/backend${PYTHONPATH:+:$PYTHONPATH}"
python scripts/bootstrap_deploy.py
exec streamlit run frontend/app.py \
  --server.address "${HOST:-0.0.0.0}" \
  --server.port "${PORT:-8501}" \
  --server.headless true
