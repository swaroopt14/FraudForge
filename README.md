# FraudForge

Closed-loop red team / blue team system for payment fraud. Built for the Mastercard Innovation Challenge 2026.

Identify emerging GenAI-powered fraud hypotheses, generate synthetic attacks, detect them with XGBoost + an autoencoder, then retrain on what slipped through.

## Stack

- Backend: Python 3.10+, FastAPI
- Models: XGBoost (HistGradientBoosting if `libomp` is missing), CTGAN / Torch GAN / bootstrap sampler, autoencoder (Torch or sklearn MLP)
- LLM: OpenAI (optional — canned hypotheses if no key)
- Data: ULB Credit Card Fraud (`Time`, `V1`–`V28`, `Amount`, `Class`) plus a narrative overlay for judge-readable SHAP
- Store: SQLite
- UI: Streamlit, Plotly, Mastercard colors (`#EB001B`, `#000000`, `#FFFFFF`) with Tailwind CDN utilities

## Quick start

```bash
cd "gff mastercard hackthon"   # repo root
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env           # optional OPENAI_API_KEY / ANTHROPIC_API_KEY

python scripts/train_all.py    # download data, train, write demo artifacts

# Terminal 1
uvicorn backend.app:app --reload --port 8000

# Terminal 2
streamlit run frontend/app.py
```

`train_all.py` is required before the first demo. It writes:

- `backend/models/detector.pkl`
- `backend/models/ctgan.pkl`
- `backend/models/autoencoder.pt`
- `backend/data/demo/scenarios.json`
- `backend/data/demo/closed_loop.json`

Individual steps: `python scripts/download_data.py`, `python scripts/train_detector.py`, `python scripts/train_ctgan.py`.

If the full ULB CSV cannot be downloaded (disk/network), `scripts/download_data.py` writes a schema-compatible synthetic table so the demo still trains.

On macOS, XGBoost needs OpenMP (`brew install libomp`). Without it the detector uses `HistGradientBoostingClassifier` automatically.

## Demo path (judges)

1. **Attack discovery** — paste threat intel, generate five hypotheses.
2. **Attack generation** — sample synthetic fraud, inspect Amount KS vs real fraud.
3. **Fraud detection** — run the three transaction scenarios; read SHAP.
4. **Closed-loop evaluation** — load precomputed before/after metrics (optional live retrain).

Streamlit talks to the in-process service (same code FastAPI exposes). FastAPI is the HTTP contract at `http://127.0.0.1:8000`.

## API

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/research/hypotheses` | LLM / fallback hypotheses |
| POST | `/attacks/generate` | CTGAN + family overlay |
| POST | `/detect` | Probability, risk, SHAP, anomaly |
| POST | `/detect/explain` | Batch SHAP |
| POST | `/evaluate/loop` | Closed-loop metrics |
| GET | `/metrics` | Detector + artifact status |
| GET | `/scenarios` | Four judge scenarios |

## Layout

```
backend/agents/     research, CTGAN, adversarial, XGBoost, autoencoder, eval, feedback
backend/app.py      FastAPI
frontend/app.py     Streamlit console
scripts/            download + train
```

See [SOLUTION_WALKTHROUGH.md](SOLUTION_WALKTHROUGH.md) for judging criteria and the four scenarios.
