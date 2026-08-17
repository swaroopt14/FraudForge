"""P0 FastAPI surface."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.core.config import CORS_ORIGINS
from app.core.db import get_engine
from app.service import (
    feature_importance_payload,
    get_simulation,
    get_transaction,
    run_simulation,
    score_transactions,
    team,
)
from app.simulation.attacks import attack_catalog

app = FastAPI(title="Adversarial Payment Defense Lab", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS or ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class GenerateIn(BaseModel):
    attack_id: str = "low_and_slow"
    intensity: str = "medium"
    transaction_count: int = Field(1000, ge=10, le=100_000)
    seed: int = 424242


class ScoreIn(BaseModel):
    transactions: list[dict[str, Any]]


@app.on_event("startup")
def _startup() -> None:
    get_engine()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/simulation/generate")
def simulation_generate(body: GenerateIn) -> dict[str, Any]:
    return run_simulation(body.attack_id, body.transaction_count, body.seed, body.intensity)


@app.post("/transactions/score")
def transactions_score(body: ScoreIn) -> dict[str, Any]:
    if not body.transactions:
        raise HTTPException(400, "transactions required")
    return {"n": len(body.transactions), "results": score_transactions(body.transactions)}


@app.get("/model/metrics")
def model_metrics() -> dict[str, Any]:
    return team().metrics


@app.get("/model/feature-importance")
def feature_importance() -> dict[str, Any]:
    return feature_importance_payload()


@app.get("/attacks")
def attacks() -> dict[str, Any]:
    return {"attacks": attack_catalog()}


@app.get("/simulations/{simulation_id}")
def simulations_get(simulation_id: str) -> dict[str, Any]:
    try:
        return get_simulation(simulation_id)
    except KeyError as exc:
        raise HTTPException(404, "simulation not found") from exc


@app.get("/transactions/{transaction_id}")
def transactions_get(transaction_id: str) -> dict[str, Any]:
    try:
        return get_transaction(transaction_id)
    except KeyError as exc:
        raise HTTPException(404, "transaction not found") from exc
