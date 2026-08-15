FROM python:3.11-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/backend \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-deploy.txt ./
COPY frontend/requirements.txt frontend/requirements.txt
RUN pip install --upgrade pip \
    && pip install -r requirements-deploy.txt

COPY backend backend
COPY frontend frontend
COPY scripts scripts
COPY .streamlit .streamlit
COPY .env.example .env.example

RUN chmod +x scripts/start_api.sh scripts/start_ui.sh \
    && mkdir -p backend/models backend/data/creditcard backend/data/demo

EXPOSE 8000 8501

HEALTHCHECK --interval=30s --timeout=5s --start-period=90s --retries=3 \
    CMD curl -fsS "http://127.0.0.1:${API_PORT:-8000}/health" || exit 1

CMD ["bash", "scripts/start_api.sh"]
