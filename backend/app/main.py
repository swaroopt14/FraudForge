"""P0 FastAPI surface."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.core.config import CORS_ORIGINS, P2_ATTACK_FAMILIES
from app.core.db import get_engine
from app.evaluation.report import FAMILY_COPY
from app.service import (
    feature_importance_payload,
    get_simulation,
    get_transaction,
    run_simulation,
    score_transactions,
    team,
)
from app.simulation.attacks import attack_catalog
from app.simulation.p2_attacks import P2_ALIASES
from app.blue_team import service as blue

app = FastAPI(title="Adversarial Payment Defense Lab", version="0.2.0")
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


class MitigateIn(BaseModel):
    action: str = "BLOCK"
    reason: str = ""


@app.post("/simulation/generate")
def simulation_generate(body: GenerateIn) -> dict[str, Any]:
    family = P2_ALIASES.get(body.attack_id, body.attack_id)
    if family in P2_ATTACK_FAMILIES:
        result = blue.run_p2_simulation(body.attack_id, body.transaction_count, body.seed, body.intensity)
        fam = str(result.get("attack_family") or family)
        result["narrative"] = FAMILY_COPY.get(fam, FAMILY_COPY["low_and_slow"])
        result.setdefault("missed_transactions", [])
        return result
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
    except KeyError:
        try:
            return blue.detection_detail(transaction_id)
        except KeyError as exc:
            raise HTTPException(404, "transaction not found") from exc


blue_api = APIRouter()


@blue_api.get("/dashboard")
def blue_dashboard() -> dict[str, Any]:
    return blue.dashboard()


@blue_api.get("/detections")
def blue_detections(attack: str | None = None, min_risk: int = 0, status: str | None = None) -> dict[str, Any]:
    rows = blue.list_detections(attack=attack, min_risk=min_risk, status=status)
    return {"detections": rows, "n": len(rows)}


@blue_api.get("/detections/{transaction_id}")
def blue_detection_detail(transaction_id: str) -> dict[str, Any]:
    try:
        return blue.detection_detail(transaction_id)
    except KeyError as exc:
        raise HTTPException(404, "transaction not found") from exc


@blue_api.get("/attack-coverage")
def blue_attack_coverage() -> dict[str, Any]:
    return blue.attack_coverage()


@blue_api.get("/network")
def blue_network_root() -> dict[str, Any]:
    return blue.network_view()


@blue_api.get("/network/{entity_id}")
def blue_network(entity_id: str) -> dict[str, Any]:
    return blue.network_view(entity_id)


@blue_api.get("/entities/{entity_type}/{entity_id}")
def blue_entity(entity_type: str, entity_id: str) -> dict[str, Any]:
    return blue.entity_view(entity_type, entity_id)


@blue_api.get("/entities/{entity_type}/{entity_id}/timeline")
def blue_timeline(entity_type: str, entity_id: str) -> dict[str, Any]:
    return {"entity_type": entity_type, "entity_id": entity_id, "events": blue.entity_timeline(entity_type, entity_id)}


@blue_api.get("/mitigation")
def blue_mitigation_queue() -> dict[str, Any]:
    return blue.mitigation_queue()


@blue_api.post("/mitigation/cluster")
def blue_isolate_cluster(body: MitigateIn | None = None) -> dict[str, Any]:
    return blue.isolate_cluster((body.reason if body else "") or "Coordinated network isolated")


@blue_api.post("/mitigation/{transaction_id}")
def blue_mitigate(transaction_id: str, body: MitigateIn) -> dict[str, Any]:
    try:
        return blue.execute_mitigation(transaction_id, body.action, body.reason)
    except KeyError as exc:
        raise HTTPException(404, "transaction not found") from exc


@blue_api.get("/reports")
def blue_report_latest() -> dict[str, Any]:
    return blue.defense_report()


@blue_api.get("/reports/{simulation_id}")
def blue_report(simulation_id: str) -> dict[str, Any]:
    return blue.defense_report(simulation_id)


@blue_api.get("/models/current")
def blue_model_current() -> dict[str, Any]:
    return blue.current_model()


@blue_api.get("/models/compare")
def blue_model_compare() -> dict[str, Any]:
    return blue.model_compare()


app.include_router(blue_api, prefix="/blue")
app.include_router(blue_api, prefix="/api/blue")
