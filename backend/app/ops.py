"""Ops payloads for the P1 lab UI. Computed from frozen model + recorded runs. No invented scores."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import confusion_matrix, precision_recall_curve
from sqlalchemy import or_

from app.core.config import (
    ALLOW_THRESHOLD,
    EVAL_DIR,
    FEATURE_COLUMNS,
    MODELS_DIR,
    REVIEW_THRESHOLD,
    STEP_UP_THRESHOLD,
)
from app.core.db import session
from app.data.schema import PaymentRow
from app.fraud.pipeline import compute_metrics
from app.risk.explain import explain_row
from app.risk.policy import decide
from app.threats.registry import get_registry

_EVAL_CACHE: dict[str, Any] | None = None


def _holdout(blue) -> dict[str, Any]:
    return dict(blue.metrics.get("lightgbm") or {})


def dashboard_summary(blue, ctrl) -> dict[str, Any]:
    hold = _holdout(blue)
    history = ctrl.history()
    generated = int(sum(int(row.get("scale") or 0) for row in history))
    run_det = [float(row["detection_rate"]) for row in history if row.get("detection_rate") is not None]
    fid = [float(row["fidelity"]) for row in history if row.get("fidelity")]
    latest = history[0] if history else None
    mean_det = float(np.mean(run_det)) if run_det else float(hold.get("recall") or 0.0)
    return {
        "transactions_simulated": generated,
        "attack_runs": len(history),
        "detection_rate": mean_det if run_det else float(hold.get("recall") or 0.0),
        "holdout_detection_rate": float(hold.get("recall") or 0.0),
        "precision": float(hold.get("precision") or 0.0),
        "recall": float(hold.get("recall") or 0.0),
        "f1": float(hold.get("f1") or 0.0),
        "pr_auc": float(hold.get("pr_auc") or 0.0),
        "false_positive_rate": float(hold.get("fpr") or 0.0),
        "attack_success_rate": float(1.0 - mean_det) if run_det else None,
        "attack_fidelity": float(np.mean(fid)) if fid else None,
        "model_version": blue.version(),
        "backend": blue.metrics.get("backend"),
        "latest_simulation": latest["simulation_id"] if latest else None,
        "n_features": len(FEATURE_COLUMNS),
    }


def recent_runs(ctrl, limit: int = 12) -> list[dict[str, Any]]:
    return [{**row, "status": "COMPLETED"} for row in ctrl.history(limit=limit)]


def list_threats(
    *,
    category: str | None = None,
    status: str | None = None,
    difficulty: str | None = None,
    simulation_ready: str | None = None,
    evidence: str | None = None,
) -> dict[str, Any]:
    threats = []
    for t in get_registry().list():
        rec = {
            "attack_id": t.attack_id,
            "name": t.name,
            "category": t.category,
            "family": t.family,
            "evidence": t.evidence_level,
            "evidence_level": t.evidence_level,
            "objective": t.objective,
            "variants": [{"id": v.id, "name": v.name} for v in t.variants],
            "variant_count": len(t.variants),
            "supported_difficulties": sorted(t.difficulty_levels.keys()),
            "detection_signals": t.detection_signals,
            "simulation_template": t.simulation_template,
            "simulation_ready": True,
            "status": "ready",
            "expected_mitigation": t.expected_mitigation,
        }
        if category and rec["category"].lower() != category.lower():
            continue
        if evidence and rec["evidence"].lower() != evidence.lower():
            continue
        if status and rec["status"] != status.lower():
            continue
        if difficulty and difficulty.upper() not in rec["supported_difficulties"]:
            continue
        if simulation_ready in {"false", "0", "no"}:
            continue
        threats.append(rec)
    return {"n": len(threats), "variants": sum(t["variant_count"] for t in threats), "threats": threats}


def threat_detail(attack_id: str) -> dict[str, Any]:
    t = get_registry().get(attack_id)
    return {
        "attack_id": t.attack_id,
        "name": t.name,
        "category": t.category,
        "evidence": t.evidence_level,
        "objective": t.objective,
        "variants": len(t.variants),
        "variant_list": [{"id": v.id, "name": v.name} for v in t.variants],
        "supported_difficulties": sorted(k.lower() for k in t.difficulty_levels),
        "detection_signals": t.detection_signals,
        "simulation_template": t.simulation_template,
        "family": t.family,
        "simulation_ready": True,
        "expected_mitigation": t.expected_mitigation,
    }


def run_metrics(run: dict[str, Any]) -> dict[str, Any]:
    metrics = run.get("metrics") or {}
    fidelity = run.get("fidelity") or {}
    if not fidelity and isinstance(metrics.get("fidelity"), dict):
        fidelity = metrics["fidelity"]
    generated = int(run.get("generated") or run.get("n") or 0)
    detection = float(run.get("detection_rate") or metrics.get("detection_rate") or metrics.get("recall") or 0.0)
    detected = int(run.get("detected") if run.get("detected") is not None else round(generated * detection))
    missed = int(run.get("missed") if run.get("missed") is not None else max(0, generated - detected))
    return {
        "simulation_id": run.get("simulation_id"),
        "attack_id": run.get("attack_id"),
        "attack_name": run.get("attack_name") or run.get("attack_id"),
        "variant_id": run.get("variant_id"),
        "difficulty": run.get("difficulty"),
        "generated": generated,
        "detected": detected,
        "missed": missed,
        "detection_rate": detection,
        "attack_success_rate": metrics.get("attack_success_rate", 1.0 - detection),
        "precision": metrics.get("precision"),
        "recall": metrics.get("recall"),
        "f1": metrics.get("f1"),
        "pr_auc": metrics.get("pr_auc"),
        "fpr": metrics.get("fpr"),
        "fidelity": fidelity.get("overall_fidelity") if isinstance(fidelity, dict) else fidelity,
        "fidelity_breakdown": fidelity if isinstance(fidelity, dict) else None,
        "model_version": run.get("model_version"),
    }


def run_signals(run: dict[str, Any]) -> dict[str, Any]:
    detected = list(run.get("detection_signals") or [])
    return {
        "simulation_id": run.get("simulation_id"),
        "detected": detected,
        "weak": [],
        "finding": run.get("finding"),
        "note": "Signals come from the threat definition. They are hypothesized channels, not proof the model used them.",
    }


def run_timeline(run: dict[str, Any]) -> dict[str, Any]:
    m = run_metrics(run)
    return {
        "simulation_id": run.get("simulation_id"),
        "stages": [
            {"id": "threat", "label": "Threat selected", "done": True, "detail": m["attack_id"]},
            {"id": "variant", "label": "Variant selected", "done": True, "detail": m["variant_id"]},
            {"id": "generate", "label": "Transactions generated", "done": True, "detail": str(m["generated"])},
            {"id": "score", "label": "Blue Team scoring", "done": True, "detail": m["model_version"]},
            {"id": "detect", "label": "Detection", "done": True, "detail": f"{m['detected']} caught / {m['missed']} missed"},
            {"id": "miss", "label": "Miss analysis", "done": True, "detail": f"{m['missed']} rows"},
            {"id": "report", "label": "Report generated", "done": bool(run.get("report"))},
        ],
    }


def run_misses(run: dict[str, Any]) -> dict[str, Any]:
    rows = run.get("missed_transactions") or []
    if rows:
        return {"simulation_id": run.get("simulation_id"), "n": run.get("missed") or len(rows), "misses": rows}
    sid = str(run.get("simulation_id") or "")
    db = session()
    try:
        stored = (
            db.query(PaymentRow)
            .filter(PaymentRow.run_id == sid, PaymentRow.fraud_probability < 0.5)
            .limit(50)
            .all()
        )
        misses = [
            {
                "transaction_id": row.transaction_id,
                "amount": row.amount,
                "fraud_probability": row.fraud_probability,
                "decision": row.decision,
                "attack_family": row.attack_family,
            }
            for row in stored
        ]
        return {"simulation_id": sid, "n": len(misses), "misses": misses}
    finally:
        db.close()


def blue_model(blue) -> dict[str, Any]:
    model_path = MODELS_DIR / "blue_team.joblib"
    last_trained = None
    if model_path.exists():
        last_trained = datetime.fromtimestamp(model_path.stat().st_mtime, tz=timezone.utc).date().isoformat()
    return {
        "model_version": blue.version(),
        "algorithm": "HistGradientBoosting" if blue.metrics.get("backend") == "hist_gbdt" else "LightGBM",
        "backend": blue.metrics.get("backend"),
        "training_dataset": "IEEE-CIS (normalized payments)",
        "features": len(getattr(blue, "feature_names", FEATURE_COLUMNS)),
        "feature_names": list(getattr(blue, "feature_names", FEATURE_COLUMNS)),
        "last_trained": last_trained,
        "thresholds": {
            "allow": ALLOW_THRESHOLD,
            "step_up": STEP_UP_THRESHOLD,
            "review": REVIEW_THRESHOLD,
            "detect": 0.5,
        },
        "holdout": _holdout(blue),
    }


def blue_features() -> dict[str, Any]:
    from app.service import feature_importance_payload

    return {
        "n": len(FEATURE_COLUMNS),
        "names": list(FEATURE_COLUMNS),
        "importance": feature_importance_payload().get("features") or [],
    }


def risk_summary() -> dict[str, Any]:
    return {
        "transaction": {"enabled": True, "phase": "P0", "source": "fraud_probability"},
        "behavior": {"enabled": True, "phase": "P0", "source": "velocity / amount_deviation / device_age"},
        "network": {"enabled": False, "phase": "P2", "source": None},
        "geo": {"enabled": False, "phase": "P2", "source": None},
        "intent": {"enabled": False, "phase": "P3", "source": None},
        "agent": {"enabled": False, "phase": "P3", "source": None},
    }


def _scored_sample(blue, payments: pd.DataFrame, n_legit: int = 1200, n_fraud: int = 400):
    legit = payments.loc[payments["fraud_label"] == 0]
    fraud = payments.loc[payments["fraud_label"] == 1]
    hold_l = legit.sample(min(len(legit), n_legit), random_state=7)
    hold_f = fraud.sample(min(len(fraud), n_fraud), random_state=7) if len(fraud) else hold_l.iloc[0:0]
    mix = pd.concat([hold_l, hold_f], ignore_index=True)
    y = mix["fraud_label"].to_numpy()
    p = blue.score(mix)
    d = [decide(float(v)) for v in p]
    return y, p, d


def eval_bundle(blue, payments: pd.DataFrame) -> dict[str, Any]:
    global _EVAL_CACHE
    key = blue.version()
    if _EVAL_CACHE and _EVAL_CACHE.get("model_version") == key:
        return _EVAL_CACHE
    y, p, decisions = _scored_sample(blue, payments)
    pred = (p >= 0.5).astype(int)
    tn, fp, fn, tp = confusion_matrix(y, pred, labels=[0, 1]).ravel()
    prec, rec, _thr = precision_recall_curve(y, p)
    sweep = [compute_metrics(y, p, threshold=float(t)) for t in np.round(np.linspace(0.01, 0.99, 21), 2)]
    counts: dict[str, int] = {"ALLOW": 0, "STEP_UP": 0, "REVIEW": 0, "BLOCK": 0}
    for d in decisions:
        counts[d] = counts.get(d, 0) + 1
    total = max(len(decisions), 1)
    bundle = {
        "model_version": key,
        "n": int(len(y)),
        "n_pos": int(y.sum()),
        "confusion": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp), "threshold": 0.5},
        "pr_curve": {
            "recall": [float(x) for x in rec.tolist()[:: max(1, len(rec) // 60)]],
            "precision": [float(x) for x in prec.tolist()[:: max(1, len(prec) // 60)]],
        },
        "threshold_sweep": sweep,
        "decision_distribution": {k: {"n": v, "share": v / total} for k, v in counts.items()},
        "metrics_at_0_5": compute_metrics(y, p, threshold=0.5),
        "source": "IEEE sample scored by the frozen detector. Not the Red Team 83% mix set.",
    }
    _EVAL_CACHE = bundle
    return bundle


def decision_distribution(blue, payments: pd.DataFrame) -> dict[str, Any]:
    db = session()
    try:
        rows = db.query(PaymentRow.decision).all()
    finally:
        db.close()
    if rows:
        counts: dict[str, int] = {"ALLOW": 0, "STEP_UP": 0, "REVIEW": 0, "BLOCK": 0}
        for (d,) in rows:
            key = str(d or "ALLOW")
            counts[key] = counts.get(key, 0) + 1
        total = max(sum(counts.values()), 1)
        return {
            "source": "scored_runs",
            "n": total,
            "distribution": {k: {"n": v, "share": v / total} for k, v in counts.items()},
        }
    bundle = eval_bundle(blue, payments)
    return {"source": "ieee_sample", "n": bundle["n"], "distribution": bundle["decision_distribution"]}


def list_transactions(
    *,
    limit: int = 50,
    offset: int = 0,
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
    db = session()
    try:
        query = db.query(PaymentRow)
        if simulation_id:
            query = query.filter(PaymentRow.run_id == simulation_id)
        if decision:
            query = query.filter(PaymentRow.decision == decision.upper())
        if attack_id:
            family = attack_id
            try:
                family = get_registry().get(attack_id).family
            except KeyError:
                pass
            query = query.filter(or_(PaymentRow.attack_family == attack_id, PaymentRow.attack_family == family))
        if risk_min is not None:
            query = query.filter(PaymentRow.fraud_probability >= risk_min)
        if risk_max is not None:
            query = query.filter(PaymentRow.fraud_probability <= risk_max)
        if outcome == "stopped":
            query = query.filter(PaymentRow.fraud_probability >= 0.5)
        elif outcome == "bypassed":
            query = query.filter(PaymentRow.fraud_probability < 0.5)
        if q:
            query = query.filter(PaymentRow.transaction_id.like(f"%{q}%"))
        for token in (customer, merchant, device, beneficiary):
            if token:
                query = query.filter(PaymentRow.payload.like(f"%{token}%"))
        total = query.count()
        rows = query.order_by(PaymentRow.id.desc()).offset(offset).limit(min(limit, 200)).all()
        items = []
        for row in rows:
            payload = json.loads(row.payload or "{}")
            items.append(
                {
                    "transaction_id": row.transaction_id,
                    "simulation_id": row.run_id,
                    "amount": row.amount,
                    "fraud_probability": row.fraud_probability,
                    "decision": row.decision,
                    "attack_id": payload.get("attack_id"),
                    "attack_family": row.attack_family or payload.get("attack_id") or payload.get("attack_family"),
                    "merchant_id": payload.get("merchant_id"),
                    "device_id": payload.get("device_id"),
                    "customer_id": payload.get("customer_id"),
                    "beneficiary_id": payload.get("beneficiary_id"),
                    "hour_of_day": payload.get("hour_of_day"),
                }
            )
        return {"n": total, "limit": limit, "offset": offset, "transactions": items}
    finally:
        db.close()


def transaction_features(payload: dict[str, Any]) -> dict[str, Any]:
    from app.service import team as _team

    names = list(getattr(_team(), "feature_names", FEATURE_COLUMNS))
    return {
        "transaction_id": payload.get("transaction_id"),
        "features": [{"feature": name, "value": payload.get(name)} for name in names],
    }


def transaction_explanation(blue, payload: dict[str, Any]) -> dict[str, Any]:
    expl = explain_row(blue.lgbm, pd.DataFrame([payload]), columns=list(getattr(blue, "feature_names", FEATURE_COLUMNS)))
    return {
        "transaction_id": payload.get("transaction_id"),
        "fraud_probability": payload.get("fraud_probability"),
        "decision": payload.get("decision"),
        "explanation": expl,
        "gap": _gap_copy(expl, payload, getattr(blue, "model_id", "BLUE-0.1.0")),
    }


def _gap_copy(expl: list[dict[str, Any]], payload: dict[str, Any], model_id: str = "BLUE-0.1.0") -> str:
    names = {e["feature"] for e in expl[:3]}
    family = str(payload.get("attack_family") or payload.get("attack_id") or "")
    if payload.get("beneficiary_is_new") in (1, 1.0) and "beneficiary_is_new" not in names:
        if str(model_id).startswith("BLUE-0.1.0"):
            return "Beneficiary novelty is on the row but is not a top model signal. BLUE-0.1.0 mostly uses merchant_risk and device_age."
        return "New-payee flag is on the row. Check beneficiary_sender_count and hours_since_pair for the remaining miss."
    if family.startswith("MUL") or "mule" in family.lower():
        if "beneficiary_sender_count" in names:
            return "Window fan-in is in the current model. Full beneficiary graph is still P2."
        return "Shared-beneficiary fan-in is not a current model feature. Network risk is P2."
    return "Top SHAP features are listed. Channels not in FEATURE_COLUMNS cannot contribute."


def defense_center(blue, ctrl) -> dict[str, Any]:
    """Blue Team view: what the detector stopped vs missed. Run stats stay separate from IEEE holdout."""
    history = ctrl.history()
    live_id = str(getattr(blue, "model_id", "") or "BLUE-0.1.0")
    board = ctrl.leaderboard(prefer_model=live_id)
    hold = _holdout(blue)
    coverage: list[dict[str, Any]] = []
    source = "red_team_runs"
    tested_board = [row for row in board if row.get("detection_rate") is not None and int(row.get("scale") or 0) > 0]
    if tested_board:
        for row in tested_board:
            tested = int(row.get("scale") or 0)
            recall = float(row.get("detection_rate") or 0.0)
            blocked = int(round(tested * recall))
            coverage.append(
                {
                    "attack_id": row.get("attack_id"),
                    "name": row.get("name") or row.get("attack_id"),
                    "tested": tested,
                    "blocked": blocked,
                    "missed": max(0, tested - blocked),
                    "recall": recall,
                    "difficulty": row.get("difficulty"),
                    "model_version": row.get("model_version"),
                    "current_detector": bool(str(row.get("model_version") or "").startswith(live_id)),
                }
            )
    else:
        source = "holdout_per_attack"
        per = blue.metrics.get("per_attack") or {}
        for family, metrics in per.items():
            tested = int(metrics.get("n_pos") or 0)
            recall = float(metrics.get("recall") or 0.0)
            blocked = int(round(tested * recall))
            coverage.append(
                {
                    "attack_id": family,
                    "name": str(family).replace("_", " "),
                    "tested": tested,
                    "blocked": blocked,
                    "missed": max(0, tested - blocked),
                    "recall": recall,
                }
            )
    coverage.sort(key=lambda row: float(row.get("recall") or 0.0))
    tested = int(sum(int(row["tested"]) for row in coverage))
    blocked = int(sum(int(row["blocked"]) for row in coverage))
    missed = max(0, tested - blocked)
    run_det = [float(row["detection_rate"]) for row in history if row.get("detection_rate") is not None]
    detection = float(np.mean(run_det)) if run_det else float(hold.get("recall") or 0.0)
    weakest = coverage[0] if coverage else None
    return {
        "model_version": blue.version(),
        "backend": blue.metrics.get("backend"),
        "source": source,
        "tested": tested,
        "blocked": blocked,
        "bypassed": missed,
        "detection_rate": detection,
        "precision": float(hold.get("precision") or 0.0),
        "recall": float(hold.get("recall") or 0.0),
        "f1": float(hold.get("f1") or 0.0),
        "pr_auc": float(hold.get("pr_auc") or 0.0),
        "false_positive_rate": float(hold.get("fpr") or 0.0),
        "holdout": hold,
        "coverage": coverage,
        "weakest": weakest,
        "latest_run": history[0] if history else None,
        "run_count": len(history),
    }


def loop_summary(blue, ctrl) -> dict[str, Any]:
    from app.blue_team.improve import load_last_loop

    stored = load_last_loop()
    if stored and stored.get("before") and stored.get("after"):
        before = stored["before"]
        after = stored["after"]
        return {
            "round": 2,
            "source": "closed_loop",
            "blue_model": stored.get("after_model") or blue.version(),
            "current": after,
            "prior": before,
            "before": before,
            "after": after,
            "delta": stored.get("delta") or {},
            "contract": stored.get("contract") or {},
            "holdout": _holdout(blue),
            "weakest": before if float(before.get("attack_success") or 0) > float(after.get("attack_success") or 0) else None,
            "note": stored.get("note")
            or "Same seed. Round 1 is the live detector. Round 2 is BLUE-0.1.3 trained on the miss.",
        }
    history = ctrl.history()
    current = history[0] if history else None
    prior = history[1] if len(history) > 1 else None
    hold = _holdout(blue)
    weakest = (ctrl.weaknesses(blue.version()) or [None])[0]
    return {
        "round": len(history),
        "source": "run_history",
        "blue_model": blue.version(),
        "current": current,
        "prior": prior,
        "holdout": hold,
        "weakest": weakest,
        "note": "Each round is one Red Team generation scored by the current detector. Use Run closed loop for a same-seed retrain report.",
    }


def evaluation_summary(blue, ctrl) -> dict[str, Any]:
    history = ctrl.history()
    generated = int(sum(int(r.get("scale") or 0) for r in history))
    detected = int(sum(int(round(float(r.get("scale") or 0) * float(r.get("detection_rate") or 0))) for r in history))
    hold = _holdout(blue)
    return {
        "red": {
            "generated": generated,
            "variants": get_registry().variant_count(),
            "fidelity": float(np.mean([float(r["fidelity"]) for r in history if r.get("fidelity")])) if history else None,
            "runs": len(history),
        },
        "blue": {
            "detected": detected,
            "missed": generated - detected,
            "precision": hold.get("precision"),
            "recall": hold.get("recall"),
            "f1": hold.get("f1"),
            "model_version": blue.version(),
        },
        "leaderboard": ctrl.leaderboard(),
    }


def attack_coverage_payload(blue, ctrl) -> dict[str, Any]:
    from app.evaluation.coverage import ENGINEERING_TARGETS, load_coverage

    stored = load_coverage()
    if stored:
        return stored
    rows = []
    for row in ctrl.leaderboard():
        generated = int(row.get("scale") or 0)
        rate = float(row.get("detection_rate") or 0.0)
        detected = int(round(generated * rate))
        rows.append(
            {
                "family": row.get("family") or row.get("attack_id"),
                "attack_id": row.get("attack_id"),
                "generated": generated,
                "detected": detected,
                "classified": None,
                "recall": rate,
                "identification_recall": None,
            }
        )
    return {
        "seed": None,
        "n_each": None,
        "baseline": {
            "model_id": getattr(blue, "model_id", "BLUE-0.1.0"),
            "model_version": blue.version(),
            "n_features": len(getattr(blue, "feature_names", [])),
            "families": rows,
            "binary": _holdout(blue),
            "macro_f1": None,
        },
        "candidate": None,
        "engineering_targets": ENGINEERING_TARGETS,
        "note": "Live leaderboard fallback. Run python -m evaluation.train_blue_011 for a fixed-seed 0.1.0 vs 0.1.1 table.",
    }


def compare_models(ctrl, model_a: str | None, model_b: str | None) -> dict[str, Any]:
    hist = ctrl.history(limit=500)
    versions = sorted({str(r.get("model_version") or "") for r in hist if r.get("model_version")})
    a = model_a or (versions[0] if versions else "")
    b = model_b or (versions[-1] if versions else "")
    return {
        "model_a": a,
        "model_b": b,
        "available_versions": versions,
        "runs_a": [r for r in hist if r.get("model_version") == a],
        "runs_b": [r for r in hist if r.get("model_version") == b],
        "note": "Fair compare uses stored seeds. Replay a run on the current detector to add a new model_version row.",
    }


def parse_benchmark_text(text: str) -> dict[str, Any]:
    checks = []
    status = "UNKNOWN"
    for line in text.splitlines():
        if "STATUS:" in line:
            status = line.split(":")[-1].strip()
        m = re.match(r"^(.+?)\s{2,}(PASS|FAIL)\s*$", line.strip())
        if m:
            checks.append({"label": m.group(1).strip(), "result": m.group(2)})
    return {"status": status, "checks": checks, "report": text}


def network_intelligence(ctrl, payments: pd.DataFrame | None = None) -> dict[str, Any]:
    """P2 lab view: shared devices/IPs and mule-like beneficiaries. Deterministic graph features."""
    from app.blue_team.context import attach_p2_features, network_summary
    from app.redteam.graph import graph_payload

    history = ctrl.history()
    preferred = next(
        (
            row
            for row in history
            if str(row.get("attack_id") or "") in {"MUL-001", "DEV-001", "IP-001", "GEO-001", "BEN-001", "MER-001"}
        ),
        history[0] if history else None,
    )
    source = "live_overlay"
    attack_id = "MUL-001"
    variant_id = "MUL-N01"
    family = "mule_network"
    rows = None
    graph = None
    if preferred:
        attack_id = str(preferred.get("attack_id") or attack_id)
        variant_id = str(preferred.get("variant_id") or variant_id)
        try:
            stored = ctrl.get_graph(str(preferred["simulation_id"]))
            if stored.get("nodes"):
                graph = stored
                source = "last_run"
        except Exception:
            graph = None
        try:
            contract = ctrl.build_contract(
                attack_id,
                variant_id=variant_id if variant_id not in {"", "None"} else None,
                difficulty=str(preferred.get("difficulty") or "MEDIUM"),
                transaction_count=min(int(preferred.get("scale") or 400), 800),
                seed=int(preferred.get("seed") or 7),
            )
            family = contract.family
            rows = ctrl.generate(contract)
        except Exception:
            rows = None
    if rows is None:
        contract = ctrl.build_contract("MUL-001", variant_id="MUL-N01", difficulty="MEDIUM", transaction_count=400, seed=7)
        family = contract.family
        attack_id = contract.attack_id
        variant_id = contract.variant_id
        rows = ctrl.generate(contract)
        source = "live_overlay"
    rows = attach_p2_features(rows)
    summary = network_summary(rows)
    if graph is None:
        graph = graph_payload(rows, family=family, attack_id=attack_id, variant_id=variant_id)
    return {
        **summary,
        "source": source,
        "attack_id": attack_id,
        "variant_id": variant_id,
        "family": family,
        "graph": graph,
        "phase": "P2",
        "note": "Graph features and deterministic network/geo scores. Not a GNN.",
    }


def p1_vs_p2_payload() -> dict[str, Any]:
    from app.evaluation.coverage import load_p1_vs_p2

    stored = load_p1_vs_p2()
    if stored:
        return stored
    return {
        "available": False,
        "note": "Run python -m evaluation.train_blue_020 to write the measured P1 vs P2 table.",
    }


def benchmark_phase(phase: str) -> dict[str, Any]:
    phase = (phase or "p1").lower()
    if phase in {"current", "p1"}:
        path = EVAL_DIR / "benchmarks" / "p1" / "last_run.txt"
        if not path.exists():
            return {"phase": "p1", "status": "NOT_RUN", "checks": [], "report": "Run: python -m evaluation.run_phase_benchmark p1"}
        parsed = parse_benchmark_text(path.read_text())
        return {"phase": "p1", **parsed, "path": str(path)}
    if phase == "p2":
        from app.evaluation.coverage import load_p1_vs_p2

        stored = load_p1_vs_p2()
        if stored and stored.get("available"):
            return {"phase": "p2", "status": "RUN", "placeholder": False, "comparison": stored}
        return {
            "phase": "p2",
            "status": "NOT_RUN",
            "placeholder": True,
            "checks": [],
            "report": "Train BLUE-0.2.0: python -m evaluation.train_blue_020",
            "comparison": stored,
        }
    return {
        "phase": phase,
        "status": "NOT_RUN",
        "checks": [],
        "report": f"{phase.upper()} is not implemented in this lab yet.",
        "placeholder": True,
    }
