"""P0/P1 FastAPI surface for the ops lab."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field

from app import ops
from app.core.config import CORS_ORIGINS, P2_ATTACK_FAMILIES, REPORTS_DIR
from app.core.db import get_engine
from app.evaluation.report import FAMILY_COPY
from app.service import (
    feature_importance_payload,
    get_simulation,
    get_transaction,
    payments,
    red_team_controller,
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


class RedTeamRunIn(BaseModel):
    attack_id: str = "ATO-001"
    variant_id: str | None = None
    intensity: str = "MEDIUM"
    difficulty: str | None = None
    transaction_count: int = Field(1000, ge=10, le=100_000)
    scale: int | None = None
    target_population: str = "normal_customers"
    seed: int = 424242


class ReplayIn(BaseModel):
    simulation_id: str


class ClosedLoopIn(BaseModel):
    attack_id: str = "BEN-001"
    variant_id: str | None = "BEN-V05"
    difficulty: str = "HIGH"
    transaction_count: int = Field(400, ge=40, le=2000)
    seed: int = 424242


class MitigateIn(BaseModel):
    action: str = "BLOCK"
    reason: str = ""


@app.on_event("startup")
def _startup() -> None:
    get_engine()


def _execute_red_team(body: RedTeamRunIn) -> dict[str, Any]:
    difficulty = (body.difficulty or body.intensity or "MEDIUM").upper()
    n = int(body.scale or body.transaction_count)
    result = red_team_controller().run(
        body.attack_id,
        variant_id=body.variant_id,
        difficulty=difficulty,
        transaction_count=n,
        seed=body.seed,
        target_population=body.target_population,
    )
    result["status"] = "completed"
    return result


def _run_or_404(simulation_id: str) -> dict[str, Any]:
    try:
        return red_team_controller().get_run(simulation_id)
    except KeyError as exc:
        raise HTTPException(404, "simulation not found") from exc


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


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


@app.get("/dashboard/summary")
def dashboard_summary() -> dict[str, Any]:
    return ops.dashboard_summary(team(), red_team_controller())


@app.get("/dashboard/recent-runs")
def dashboard_recent() -> dict[str, Any]:
    return {"runs": ops.recent_runs(red_team_controller())}


@app.get("/attacks")
def attacks() -> dict[str, Any]:
    return {"attacks": attack_catalog()}


@app.get("/simulations/{simulation_id}")
def simulations_get(simulation_id: str) -> dict[str, Any]:
    try:
        return get_simulation(simulation_id)
    except KeyError as exc:
        raise HTTPException(404, "simulation not found") from exc


@app.get("/threats")
def threats_list(
    category: str | None = None,
    status: str | None = None,
    difficulty: str | None = None,
    simulation_ready: str | None = None,
    evidence: str | None = None,
) -> dict[str, Any]:
    return ops.list_threats(
        category=category,
        status=status,
        difficulty=difficulty,
        simulation_ready=simulation_ready,
        evidence=evidence,
    )


@app.get("/taxonomy")
def taxonomy() -> dict[str, Any]:
    from app.threats.taxonomy import taxonomy_payload

    return taxonomy_payload()


@app.get("/threats/{attack_id}")
def threats_get(attack_id: str) -> dict[str, Any]:
    try:
        return ops.threat_detail(attack_id)
    except KeyError as exc:
        raise HTTPException(404, "threat not found") from exc


@app.post("/red-team/run")
def red_team_run(body: RedTeamRunIn) -> dict[str, Any]:
    return _execute_red_team(body)


@app.post("/red-team/runs")
def red_team_runs_create(body: RedTeamRunIn) -> dict[str, Any]:
    return _execute_red_team(body)


@app.post("/red-team/replay")
def red_team_replay(body: ReplayIn) -> dict[str, Any]:
    try:
        result = red_team_controller().replay(body.simulation_id)
    except KeyError as exc:
        raise HTTPException(404, "simulation not found") from exc
    result["status"] = "completed"
    return result


@app.get("/red-team/runs")
def red_team_runs_list() -> dict[str, Any]:
    return {"runs": ops.recent_runs(red_team_controller(), limit=100)}


@app.get("/red-team/runs/{simulation_id}")
def red_team_run_get(simulation_id: str) -> dict[str, Any]:
    return _run_or_404(simulation_id)


@app.post("/red-team/runs/{simulation_id}/replay")
def red_team_run_replay(simulation_id: str) -> dict[str, Any]:
    try:
        result = red_team_controller().replay(simulation_id)
    except KeyError as exc:
        raise HTTPException(404, "simulation not found") from exc
    result["status"] = "completed"
    return result


@app.get("/red-team/runs/{simulation_id}/report")
def red_team_report(simulation_id: str) -> dict[str, Any]:
    run = _run_or_404(simulation_id)
    return {"simulation_id": simulation_id, "report": run.get("report", "")}


@app.get("/red-team/runs/{simulation_id}/metrics")
def red_team_run_metrics(simulation_id: str) -> dict[str, Any]:
    return ops.run_metrics(_run_or_404(simulation_id))


@app.get("/red-team/runs/{simulation_id}/signals")
def red_team_run_signals(simulation_id: str) -> dict[str, Any]:
    return ops.run_signals(_run_or_404(simulation_id))


@app.get("/red-team/runs/{simulation_id}/timeline")
def red_team_run_timeline(simulation_id: str) -> dict[str, Any]:
    return ops.run_timeline(_run_or_404(simulation_id))


@app.get("/red-team/runs/{simulation_id}/misses")
def red_team_run_misses(simulation_id: str) -> dict[str, Any]:
    return ops.run_misses(_run_or_404(simulation_id))


@app.get("/red-team/runs/{simulation_id}/graph")
def red_team_graph(simulation_id: str) -> dict[str, Any]:
    try:
        return red_team_controller().get_graph(simulation_id)
    except KeyError as exc:
        raise HTTPException(404, "simulation not found") from exc


@app.get("/red-team/leaderboard")
def red_team_leaderboard() -> dict[str, Any]:
    return {"leaderboard": red_team_controller().leaderboard()}


@app.get("/red-team/history")
def red_team_history() -> dict[str, Any]:
    return {"history": red_team_controller().history()}


@app.get("/red-team/benchmarks")
def red_team_benchmarks() -> dict[str, Any]:
    return ops.benchmark_phase("p1")


@app.get("/blue-team")
def blue_team_lab() -> dict[str, Any]:
    blue = team()
    ctrl = red_team_controller()
    version = blue.version()
    return {
        "model_version": version,
        "backend": blue.metrics.get("backend"),
        "holdout": blue.metrics.get("lightgbm") or {},
        "logreg": blue.metrics.get("logreg") or {},
        "per_attack": blue.metrics.get("per_attack") or {},
        "features": feature_importance_payload().get("features") or [],
        "weaknesses": ctrl.weaknesses(version),
        "history": ctrl.history(),
        "leaderboard": ctrl.leaderboard(),
        "model": ops.blue_model(blue),
        "risk": ops.risk_summary(),
    }


@app.get("/blue-team/model")
def blue_team_model() -> dict[str, Any]:
    return ops.blue_model(team())


@app.get("/blue-team/features")
def blue_team_features() -> dict[str, Any]:
    return ops.blue_features()


@app.get("/blue-team/defense")
def blue_team_defense() -> dict[str, Any]:
    return ops.defense_center(team(), red_team_controller())


@app.get("/blue-team/network")
def blue_team_network() -> dict[str, Any]:
    return ops.network_intelligence(red_team_controller(), payments())


@app.get("/loop/summary")
def loop_round() -> dict[str, Any]:
    return ops.loop_summary(team(), red_team_controller())


@app.get("/evaluate/loop")
def evaluate_loop_get() -> dict[str, Any]:
    return ops.loop_summary(team(), red_team_controller())


@app.post("/evaluate/loop")
def evaluate_loop_run(body: ClosedLoopIn) -> dict[str, Any]:
    from app.blue_team.improve import run_closed_loop

    return run_closed_loop(
        payments(),
        team(),
        attack_id=body.attack_id,
        variant_id=body.variant_id,
        difficulty=body.difficulty,
        transaction_count=body.transaction_count,
        seed=body.seed,
        persist=True,
    )


@app.get("/blue-team/risk-summary")
def blue_team_risk() -> dict[str, Any]:
    return ops.risk_summary()


@app.get("/blue-team/decision-distribution")
def blue_team_decisions() -> dict[str, Any]:
    return ops.decision_distribution(team(), payments())


@app.get("/transactions")
def transactions_list(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    risk_min: float | None = None,
    risk_max: float | None = None,
    decision: str | None = None,
    attack_id: str | None = None,
    simulation_id: str | None = None,
    q: str | None = None,
    customer: str | None = None,
    merchant: str | None = None,
    device: str | None = None,
    beneficiary: str | None = None,
    outcome: str | None = None,
) -> dict[str, Any]:
    return ops.list_transactions(
        limit=limit,
        offset=offset,
        risk_min=risk_min,
        risk_max=risk_max,
        decision=decision,
        attack_id=attack_id,
        simulation_id=simulation_id,
        q=q,
        customer=customer,
        merchant=merchant,
        device=device,
        beneficiary=beneficiary,
        outcome=outcome,
    )


@app.get("/transactions/{transaction_id}")
def transactions_get(transaction_id: str) -> dict[str, Any]:
    try:
        return get_transaction(transaction_id)
    except KeyError:
        try:
            return blue.detection_detail(transaction_id)
        except KeyError as exc:
            raise HTTPException(404, "transaction not found") from exc


@app.get("/transactions/{transaction_id}/features")
def transactions_features(transaction_id: str) -> dict[str, Any]:
    try:
        return ops.transaction_features(get_transaction(transaction_id))
    except KeyError as exc:
        raise HTTPException(404, "transaction not found") from exc


@app.get("/transactions/{transaction_id}/explanation")
def transactions_explanation(transaction_id: str) -> dict[str, Any]:
    try:
        return ops.transaction_explanation(team(), get_transaction(transaction_id))
    except KeyError as exc:
        raise HTTPException(404, "transaction not found") from exc


@app.get("/model/metrics")
def model_metrics() -> dict[str, Any]:
    blue = team()
    return {**blue.metrics, "model_version": blue.version()}


@app.get("/model/feature-importance")
def feature_importance() -> dict[str, Any]:
    return feature_importance_payload()


@app.get("/model/confusion-matrix")
def model_confusion() -> dict[str, Any]:
    bundle = ops.eval_bundle(team(), payments())
    return {**bundle["confusion"], "model_version": bundle["model_version"], "source": bundle["source"]}


@app.get("/model/pr-curve")
def model_pr_curve() -> dict[str, Any]:
    bundle = ops.eval_bundle(team(), payments())
    return {"model_version": bundle["model_version"], "source": bundle["source"], **bundle["pr_curve"]}


@app.get("/model/threshold-sweep")
def model_threshold_sweep() -> dict[str, Any]:
    bundle = ops.eval_bundle(team(), payments())
    return {"model_version": bundle["model_version"], "source": bundle["source"], "sweep": bundle["threshold_sweep"]}


@app.get("/evaluation/summary")
def evaluation_summary() -> dict[str, Any]:
    return ops.evaluation_summary(team(), red_team_controller())


@app.get("/evaluation/attack-matrix")
def evaluation_matrix() -> dict[str, Any]:
    return {"rows": red_team_controller().leaderboard()}


@app.get("/evaluation/attack-coverage")
def evaluation_attack_coverage() -> dict[str, Any]:
    return ops.attack_coverage_payload(team(), red_team_controller())


@app.get("/evaluation/compare")
def evaluation_compare(model_a: str | None = None, model_b: str | None = None) -> dict[str, Any]:
    return ops.compare_models(red_team_controller(), model_a, model_b)


@app.get("/evaluation/p1-vs-p2")
def evaluation_p1_vs_p2() -> dict[str, Any]:
    return ops.p1_vs_p2_payload()


@app.get("/benchmarks/current")
def benchmarks_current() -> dict[str, Any]:
    return ops.benchmark_phase("p1")


@app.get("/benchmarks/{phase}")
def benchmarks_phase(phase: str) -> dict[str, Any]:
    return ops.benchmark_phase(phase)


@app.get("/benchmarks/{phase}/details")
def benchmarks_details(phase: str) -> dict[str, Any]:
    return ops.benchmark_phase(phase)


@app.get("/models/registry")
def models_registry() -> dict[str, Any]:
    from app.core.model_registry import team_versions

    return team_versions()


class StrategyIn(BaseModel):
    model_config = ConfigDict(extra="allow")

    attack_id: str | None = None
    variant_id: str | None = None
    difficulty: str = "medium"
    mutation_strategy: dict[str, Any] | None = None
    scale: int | None = None
    claim_novel: bool = False


@app.post("/red-team/recommend")
def red_team_recommend() -> dict[str, Any]:
    from app.red_team.models.attack_strategy import RedTeamAttackIntelligence

    intel = RedTeamAttackIntelligence.load()
    return intel.recommend()


@app.post("/red-team/validate")
def red_team_validate(body: StrategyIn) -> dict[str, Any]:
    from app.red_team.validator import validate_strategy

    return validate_strategy(body.model_dump(), claim_novel=body.claim_novel)


@app.get("/red-team/runs/{simulation_id}/blue-report")
def red_team_blue_report(simulation_id: str) -> dict[str, Any]:
    import json

    run = _run_or_404(simulation_id)
    if run.get("blue_report"):
        return run["blue_report"]
    path = REPORTS_DIR / f"blueteam_{simulation_id}.json"
    if path.exists():
        return json.loads(path.read_text())
    raise HTTPException(404, "blue report not found")


@app.get("/red-team/runs/{simulation_id}/feedback")
def red_team_feedback(simulation_id: str) -> dict[str, Any]:
    run = _run_or_404(simulation_id)
    return {
        "simulation_id": simulation_id,
        "red_feedback": run.get("red_feedback"),
        "blue_feedback": run.get("blue_feedback"),
        "linked": bool(run.get("red_feedback") and run.get("blue_feedback")),
    }


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
