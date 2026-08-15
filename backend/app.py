"""FastAPI surface for FraudForge agents."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from contextlib import asynccontextmanager

BACKEND = Path(__file__).resolve().parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from service import get_service, load_scenarios  # noqa: E402


@asynccontextmanager
async def lifespan(_app: FastAPI):
    get_service().load()
    yield


app = FastAPI(title="FraudForge", version="1.0.0", lifespan=lifespan)
_cors = [o.strip() for o in os.getenv("FRAUDFORGE_CORS_ORIGINS", "*").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors or ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ThreatIntelIn(BaseModel):
    threat_intel: str = ""
    fetch_live: bool = False


class GenerateIn(BaseModel):
    n_samples: int = Field(500, ge=10, le=5000)
    family: str | None = "mixed"
    intensity: str = "medium"
    from_legitimate: bool = False


class DetectIn(BaseModel):
    transactions: list[dict[str, Any]]
    explain: bool = False


class ExplainIn(BaseModel):
    transactions: list[dict[str, Any]]
    top_k: int = 5


class LoopIn(BaseModel):
    live: bool = False


class SimStartIn(BaseModel):
    scenario_id: str = "agent_destination_substitution"
    mode: str = "full"
    payment_rail: str | None = None
    seed: int = 42


class DemoRedIn(BaseModel):
    family: str = "prompt_injection_pay"
    intensity: str = "medium"


class DemoBlueIn(BaseModel):
    transaction: dict[str, Any] | None = None


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/metrics")
def metrics() -> dict[str, Any]:
    return get_service().metrics()


@app.get("/scenarios")
def scenarios() -> list[dict[str, Any]]:
    return load_scenarios()


@app.get("/research/intel")
def intel_sources() -> dict[str, Any]:
    sources = get_service().intel_sources()
    return {"n": len(sources), "sources": sources}


@app.get("/research/catalog")
def catalog() -> dict[str, Any]:
    from attack_catalog import (
        ATTACK_CATALOG,
        CORE_ATTACK_VECTORS,
        DIVERSITY_TARGET,
        SIMULATABLE_FAMILIES,
        TAXONOMY,
    )

    identified = [fid for fid, meta in ATTACK_CATALOG.items() if not meta.get("simulatable")]
    return {
        "n": len(ATTACK_CATALOG),
        "simulatable": SIMULATABLE_FAMILIES,
        "identified_only": identified,
        "taxonomy": TAXONOMY,
        "n_taxonomy": len(TAXONOMY),
        "diversity_target": DIVERSITY_TARGET,
        "core_vectors": CORE_ATTACK_VECTORS,
        "provider": get_service().research.provider,
        "graph_runtime": getattr(get_service().research, "graph_runtime", None),
        "families": ATTACK_CATALOG,
    }


@app.post("/research/hypotheses")
def hypotheses(body: ThreatIntelIn) -> dict[str, Any]:
    result = get_service().discover(body.threat_intel, fetch_live=body.fetch_live)
    result["fallback"] = get_service().research.using_fallback
    result.setdefault("provider", get_service().research.provider)
    return result


@app.post("/attacks/generate")
def generate(body: GenerateIn) -> dict[str, Any]:
    try:
        return get_service().generate_attacks(
            n_samples=body.n_samples,
            family=body.family,
            intensity=body.intensity,
            from_legitimate=body.from_legitimate,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/research/novelty")
def novelty() -> dict[str, Any]:
    try:
        return get_service().novelty_coverage()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/detect")
def detect(body: DetectIn) -> dict[str, Any]:
    if not body.transactions:
        raise HTTPException(status_code=400, detail="No transactions supplied")
    try:
        return get_service().detect_rows(body.transactions, explain=body.explain)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/detect/explain")
def explain(body: ExplainIn) -> dict[str, Any]:
    svc = get_service()
    if svc.detector is None:
        raise HTTPException(status_code=503, detail="Detector not loaded")
    import pandas as pd

    from features import ensure_narrative

    df = ensure_narrative(pd.DataFrame(body.transactions))
    table = svc.detector.explain(df, top_k=body.top_k)
    return {"explanation": table.to_dict(orient="records")}


@app.post("/demo/red")
def demo_red(body: DemoRedIn) -> dict[str, Any]:
    try:
        return get_service().run_red_demo(family=body.family, intensity=body.intensity)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/demo/blue")
def demo_blue(body: DemoBlueIn) -> dict[str, Any]:
    try:
        return get_service().run_blue_demo(transaction=body.transaction)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/evaluate/loop")
def evaluate_loop(body: LoopIn) -> dict[str, Any]:
    try:
        return get_service().closed_loop(live=body.live)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/simulation/scenarios")
def sim_scenarios() -> dict[str, Any]:
    rows = get_service().list_sim_scenarios()
    return {"n": len(rows), "scenarios": rows}


@app.post("/simulation/start")
def sim_start(body: SimStartIn) -> dict[str, Any]:
    try:
        return get_service().start_simulation(
            body.scenario_id,
            mode=body.mode,
            payment_rail=body.payment_rail,
            seed=body.seed,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/simulation/{simulation_id}")
def sim_get(simulation_id: str) -> dict[str, Any]:
    try:
        return get_service().get_simulation(simulation_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="simulation not found") from exc


@app.post("/simulation/{simulation_id}/next")
def sim_next(simulation_id: str) -> dict[str, Any]:
    try:
        return get_service().step_simulation(simulation_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="simulation not found") from exc


@app.post("/simulation/{simulation_id}/run")
def sim_run(simulation_id: str) -> dict[str, Any]:
    try:
        return get_service().run_simulation(simulation_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="simulation not found") from exc


@app.post("/simulation/{simulation_id}/reset")
def sim_reset(simulation_id: str) -> dict[str, Any]:
    try:
        return get_service().reset_simulation(simulation_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="simulation not found") from exc


@app.post("/evaluation/retrain")
def sim_retrain(scenario_id: str = "agent_destination_substitution") -> dict[str, Any]:
    try:
        return get_service().replay_simulation(scenario_id)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/evaluation/{simulation_id}")
def sim_eval(simulation_id: str) -> dict[str, Any]:
    try:
        state = get_service().get_simulation(simulation_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="simulation not found") from exc
    return {
        "simulation_id": simulation_id,
        "decision": (state.get("final_decision") or {}).get("decision"),
        "learning": state.get("learning"),
        "failure_artifact": state.get("failure_artifact"),
        "evaluation": "SIMULATED EVALUATION",
    }


@app.post("/simulation/flagship")
def sim_flagship() -> dict[str, Any]:
    return get_service().flagship_demo()
