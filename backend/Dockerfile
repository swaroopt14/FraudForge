FROM python:3.11-slim

WORKDIR /lab/backend

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt /lab/backend/requirements.txt
RUN pip install --no-cache-dir -r /lab/backend/requirements.txt

COPY backend /lab/backend
COPY scripts /lab/scripts

ENV PYTHONPATH=/lab/backend
ENV LAB_ROOT=/lab
ENV HOST=0.0.0.0
ENV PORT=8000

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
