# FraudForge

Closed-loop **red team / blue team** system for Mastercard-style payment fraud.

Identify emerging GenAI attack families, generate synthetic transactions, detect them with a hybrid classifier, then retrain on what slipped through.

Product detail: [PROJECT.md](PROJECT.md)

This repository is ready to run locally or deploy as containers. Secrets, the ULB CSV, and trained model files stay out of git.

---

## What ships vs what you generate

| In git | Generated on first boot / train |
| --- | --- |
| Catalog, overlays, API, Streamlit console | `backend/models/detector.pkl` |
| Demo intel, scenarios, closed-loop JSON | ULB `creditcard.csv` (or a synthetic stand-in) |
| Tests and CI | SQLite + simulation event logs |

Never commit `.env`. Copy `.env.example`.

---

## Local run

Python 3.11+ recommended.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env

python scripts/bootstrap_deploy.py

# API  http://127.0.0.1:8000/health
uvicorn backend.app:app --host 0.0.0.0 --port 8000

# Console  http://127.0.0.1:8501
streamlit run frontend/app.py
```

On macOS, if NumPy fails to load:

```bash
unset DYLD_LIBRARY_PATH
```

XGBoost needs OpenMP (`brew install libomp`). Without it the detector uses HistGradientBoosting.

Optional full train (CTGAN + autoencoder + live closed loop):

```bash
python scripts/train_all.py
```

Optional LLM for Identify: set `NVIDIA_API_KEY` or `OPENAI_API_KEY` in `.env`. Without a key, discovery uses the local catalog.

---

## Docker

```bash
cp .env.example .env
docker compose up --build
```

- API: http://127.0.0.1:8000/health
- Console: http://127.0.0.1:8501

First boot trains the detector if `detector.pkl` is missing (a few minutes). Models persist in a Docker volume.

API only:

```bash
docker build -t fraudforge .
docker run --rm -p 8000:8000 --env-file .env fraudforge
```

UI only (same image):

```bash
docker run --rm -p 8501:8501 -e PORT=8501 --env-file .env fraudforge bash scripts/start_ui.sh
```

---

## Hosted deploy

Both processes bind `0.0.0.0` and read `PORT`.

| Target | How |
| --- | --- |
| **Docker host / VM** | `docker compose up --build -d` |
| **Render / Railway / Fly** | Web service from this Dockerfile. Set start command `bash scripts/start_api.sh` (API) or `bash scripts/start_ui.sh` (console). Map `PORT`. |
| **Streamlit Community Cloud** | App file `streamlit_app.py`. Python 3.11. Uses `packages.txt` (`libgomp1`) and `requirements-deploy.txt` as the dependency file if you point the cloud settings at it; otherwise install `requirements.txt` (heavier). |

Set these on the host:

```
HOST=0.0.0.0
PORT=<platform port>
FRAUDFORGE_API_URL=https://<your-api-host>
FRAUDFORGE_CORS_ORIGINS=https://<your-ui-host>
```

LLM keys stay in the platform secret store, not in git.

Health check for the API: `GET /health` → `{"status":"ok"}`.

---

## Tests

```bash
source .venv/bin/activate
python -m pytest tests -q
```

CI runs the same suite on every push to `main` (`.github/workflows/ci.yml`).

---

## API

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/health` | Liveness |
| GET | `/metrics` | Model and artifact status |
| GET | `/research/catalog` | Attack catalog |
| POST | `/research/hypotheses` | Identify |
| POST | `/attacks/generate` | Synthetic rows |
| POST | `/detect` | Batch score |
| POST | `/evaluate/loop` | Closed-loop metrics |
| POST | `/simulation/start` | Payment simulator |

---

## Layout

```
backend/app.py          FastAPI
frontend/app.py        Streamlit console
streamlit_app.py       Cloud entrypoint
scripts/bootstrap_deploy.py   First-boot data + detector
scripts/start_api.sh   Container / host API
scripts/start_ui.sh    Container / host UI
Dockerfile             API image (UI uses the same image)
docker-compose.yml     API + console
```
