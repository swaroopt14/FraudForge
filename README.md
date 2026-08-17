# Adversarial Payment Defense Lab

P0 lab: IEEE-CIS payments → five seeded attack families → Logistic Regression + LightGBM → risk policy + SHAP → a generated adversarial report.

No card-network brand names appear in the product.

## Layout

```
backend/app/{api,core,data,fraud,risk,simulation,evaluation}
frontend/          Next.js command center
data/{raw,processed,synthetic}
models/
evaluation/reports/
scripts/
```

## Quick start (local)

```bash
cd adversarial-payment-defense-lab
python -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements.txt
export PYTHONPATH=backend
python scripts/ingest.py
python scripts/train.py
uvicorn app.main:app --app-dir backend --reload --port 8000
```

In another shell:

```bash
cd frontend
npm install
echo 'NEXT_PUBLIC_API_URL=http://127.0.0.1:8000' > .env.local
npm run dev
```

IEEE train files are read from `../data/ieee-fraud-detection/` or `IEEE_DIR`. Default subsample is 80k (`IEEE_SAMPLE_N`).

## RUN RED TEAM TEST

```bash
python scripts/run_red_team_test.py --attack low_and_slow --n 10000 --seed 424242
```

Writes `evaluation/reports/run_*.txt` and JSON metrics. Detection numbers are computed from the run.

## Docker

```bash
docker compose up --build
```

Compose starts `postgres`, `backend` (`GET /health`), and `frontend`. Mounts the IEEE directory read-only.

## Tests

```bash
cd backend && pytest
```

Covers schema, simulator seeds, models, policy, fidelity, API generate→score→report, and a smaller red-team workflow.

## Policy

`fraud_probability` is not the decision.

| Band | Action |
|---|---|
| 0.00–0.30 | ALLOW |
| 0.30–0.60 | STEP_UP |
| 0.60–0.80 | REVIEW |
| 0.80–1.00 | BLOCK |

On macOS, LightGBM needs `libomp`. If it is missing, the lab falls back to HistGradientBoosting and still compares it to Logistic Regression.

## Out of P0

Threat library expansion, graph/geo, agents, closed-loop retrain, Kafka, 1M-scale.
