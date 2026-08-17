"""P2 ingest, score, investigate, mitigate."""

from __future__ import annotations

import json
import time
import uuid
from collections import Counter
from typing import Any

import numpy as np
import pandas as pd

from app.blue_team import store
from app.blue_team.features import attach_p2_features
from app.blue_team.graph import beneficiary_profile, cluster_stats, neighborhood
from app.blue_team.models import CLS_MODEL_ID, FRAUD_MODEL_ID, P0_MODEL_ID, BlueTeamV2
from app.blue_team.reports import render_defense_report
from app.blue_team.risk import component_risks, evidence_signals, mitigation_reason, recommend_action, risk_score
from app.core.config import ALL_ATTACK_FAMILIES, EVAL_DIR, MODELS_DIR, P2_ATTACK_FAMILIES, RANDOM_STATE, ensure_dirs
from app.fraud.pipeline import compute_metrics, prepare_split
from app.simulation.attacks import generate_attacks, generate_mixed_attacks
from app.simulation.p2_attacks import generate_mixed_p2_attacks, generate_p2_attacks

_p2: BlueTeamV2 | None = None


def _clock(ts: Any) -> str:
    t = int(abs(float(ts or 0))) % 86400
    return f"{t // 3600:02d}:{(t % 3600) // 60:02d}:{t % 60:02d}"


def _plain(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    if isinstance(value, np.generic):
        return value.item()
    try:
        if value is not None and not isinstance(value, (str, bytes, bool)) and pd.isna(value):
            return None
    except (ValueError, TypeError):
        pass
    return value


def p2_team() -> BlueTeamV2:
    global _p2
    if _p2 is None:
        path = MODELS_DIR / "blue_fraud_0_2_0.joblib"
        if path.exists():
            _p2 = BlueTeamV2.load(path)
        else:
            _p2 = train_p2()
    return _p2


def train_p2(payments: pd.DataFrame | None = None, n_each: int = 200) -> BlueTeamV2:
    from app.service import payments as load_pay

    source = payments if payments is not None else load_pay()
    p0_atk = generate_mixed_attacks(source, n_each=max(40, n_each // 2))
    p2_atk = generate_mixed_p2_attacks(source, n_each=n_each)
    p2_parts = [attach_p2_features(part) for _, part in p2_atk.groupby("attack_family", sort=False)]
    attacks = pd.concat([p0_atk, *p2_parts], ignore_index=True).sample(frac=1.0, random_state=RANDOM_STATE)
    train, test = prepare_split(source, attacks)
    team = BlueTeamV2()
    team.train(train, test)
    per_attack: dict[str, Any] = {}
    legit = test.loc[test["fraud_label"] == 0]
    hold = legit.sample(min(len(legit), 400), random_state=0) if len(legit) else legit
    for family in ALL_ATTACK_FAMILIES:
        atk = test.loc[test["attack_family"] == family]
        if atk.empty:
            try:
                atk = generate_p2_attacks(source, family, 120, seed=9) if family in P2_ATTACK_FAMILIES else generate_attacks(source, family, 120, seed=9)
            except ValueError:
                continue
        mix = pd.concat([hold, atk], ignore_index=True) if len(hold) else atk
        scores = team.score(atk)
        detected = int((scores >= 0.5).sum())
        generated = int(len(atk))
        per_attack[family] = {
            **compute_metrics(mix["fraud_label"].to_numpy(), team.score(mix)),
            "generated": generated,
            "detected": detected,
            "missed": generated - detected,
            "attack_recall": float(detected / max(generated, 1)),
        }
    team.metrics["per_attack"] = per_attack
    team.metrics["model_id"] = FRAUD_MODEL_ID
    p0 = _p0_on_p2(source, team)
    team.metrics["p0_comparison"] = p0
    ensure_dirs()
    import json

    (EVAL_DIR / "p2_comparison.json").write_text(
        json.dumps({"p0": p0, "p2": team.metrics.get("lightgbm"), "per_attack": per_attack}, indent=2, default=str)
    )
    team.save()
    global _p2
    _p2 = team
    store.put_stream(p2_metrics=team.metrics)
    return team


def _p0_on_p2(source: pd.DataFrame, p2: BlueTeamV2) -> dict[str, Any]:
    """How P0 (no context features) scores the same coordinated attacks."""
    from app.service import team as p0_team

    try:
        blue0 = p0_team()
    except Exception:  # noqa: BLE001
        return {}
    out: dict[str, Any] = {"model_id": P0_MODEL_ID}
    for family in P2_ATTACK_FAMILIES:
        atk = generate_p2_attacks(source, family, 150, seed=11)
        legit = source.loc[source["fraud_label"] == 0].head(150)
        mix = pd.concat([atk, legit], ignore_index=True) if len(legit) else atk
        out[family] = {
            "p0": compute_metrics(mix["fraud_label"].to_numpy(), blue0.score(mix)),
            "p2": compute_metrics(mix["fraud_label"].to_numpy(), p2.score(mix)),
        }
    return out


def run_p2_simulation(
    attack_id: str,
    transaction_count: int,
    seed: int,
    intensity: str = "medium",
) -> dict[str, Any]:
    from app.service import payments

    t0 = time.perf_counter()
    source = payments()
    if attack_id in P2_ATTACK_FAMILIES or attack_id in {"MUL-001", "DEV-001", "IP-001", "GEO-001", "CTX-001"}:
        rows = generate_p2_attacks(source, attack_id, transaction_count, seed=seed, intensity=intensity)
    else:
        rows = generate_attacks(source, attack_id, transaction_count, seed=seed, intensity=intensity)
    family = str(rows["attack_family"].iloc[0])
    variant = str(rows["variant_id"].iloc[0]) if "variant_id" in rows.columns else family
    rows = attach_p2_features(rows)
    t_feat = time.perf_counter()
    blue = p2_team()
    proba = blue.score(rows)
    t_det = time.perf_counter()
    classified = blue.classify(rows)
    t_cls = time.perf_counter()

    detections: list[dict[str, Any]] = []
    y = rows["fraud_label"].to_numpy()
    actions: list[str] = []
    for i, row in rows.reset_index(drop=True).iterrows():
        rec = _plain(row.to_dict())
        rec["fraud_probability"] = float(proba[i])
        rec["attack_prediction"] = classified[i]["family"]
        rec["classification_confidence"] = classified[i]["confidence"]
        rec["risk_score"] = risk_score(pd.Series(rec))
        rec["signals"] = evidence_signals(pd.Series(rec))
        rec["action"] = recommend_action(pd.Series(rec), rec["fraud_probability"])
        rec["decision"] = rec["action"]
        rec["reason"] = mitigation_reason(rec["attack_prediction"], rec["signals"])
        rec["missed"] = int(y[i]) == 1 and rec["fraud_probability"] < 0.5
        rec["clock"] = _clock(rec.get("timestamp"))
        actions.append(rec["action"])
        detections.append(rec)

    legit = source.loc[source["fraud_label"] == 0]
    if len(legit):
        hold = legit.sample(min(len(legit), max(200, transaction_count // 5)), random_state=seed)
        mix = pd.concat([rows, attach_p2_features(hold)], ignore_index=True)
        metrics = compute_metrics(mix["fraud_label"].to_numpy(), blue.score(mix))
    else:
        metrics = compute_metrics(y, proba)
    attack_metrics = compute_metrics(y, proba)
    metrics["detection_rate"] = attack_metrics["recall"]
    missed_n = int(sum(1 for d in detections if d["missed"]))
    detected_n = int(transaction_count - missed_n)
    ident = Counter(d["attack_prediction"] for d in detections)
    ident_share = {k: v / max(len(detections), 1) for k, v in ident.items()}
    mit = Counter(actions)
    t_mit = time.perf_counter()
    timing = {
        "time_to_detect_s": round(t_det - t0, 3),
        "time_to_classify_s": round(t_cls - t0, 3),
        "time_to_mitigate_s": round(t_mit - t0, 3),
        "feature_ms": round((t_feat - t0) * 1000, 2),
        "detect_ms": round((t_det - t_feat) * 1000, 2),
    }
    run_id = uuid.uuid4().hex[:8]
    gap = {
        "primary": "Individual rows resemble legitimate spend; coordination is in the graph."
        if family in P2_ATTACK_FAMILIES
        else "See per-family recall.",
        "recommended": "Keep rolling beneficiary fan-in / shared device / IP features on the stream.",
    }
    report_payload = {
        "simulation_id": run_id,
        "attack_family": family,
        "variant_id": variant,
        "model_id": FRAUD_MODEL_ID,
        "transactions": transaction_count,
        "detected": detected_n,
        "missed": missed_n,
        "metrics": metrics,
        "identification": ident_share,
        "timing": timing,
        "mitigation": dict(mit),
        "gap": gap,
    }
    report = render_defense_report(report_payload)
    coverage = {fam: float((blue.metrics.get("per_attack") or {}).get(fam, {}).get("recall") or 0.0) for fam in ALL_ATTACK_FAMILIES}
    store.put_stream(
        simulation_id=run_id,
        attack_family=family,
        variant_id=variant,
        model_id=FRAUD_MODEL_ID,
        detections=detections,
        frame=rows,
        mitigations={},
        report=report,
        metrics=metrics,
        coverage=coverage,
        timing=timing,
        p2_metrics=blue.metrics,
        report_payload=report_payload,
    )
    preview = [
        {
            "transaction_id": d["transaction_id"],
            "attack_prediction": d["attack_prediction"],
            "risk_score": d["risk_score"],
            "classification_confidence": d["classification_confidence"],
            "action": d["action"],
            "decision": d["action"],
            "fraud_probability": d["fraud_probability"],
            "clock": d.get("clock"),
        }
        for d in detections[:12]
    ]
    missed_transactions = [d for d in detections if d.get("missed")][:50]
    _persist_p2_run(run_id, family, transaction_count, seed, intensity, metrics, report, detections)
    return {
        "simulation_id": run_id,
        "attack_family": family,
        "variant_id": variant,
        "model_id": FRAUD_MODEL_ID,
        "classifier_id": CLS_MODEL_ID,
        "generated": transaction_count,
        "detected": detected_n,
        "missed": missed_n,
        "detection_rate": float(metrics["recall"]),
        "metrics": metrics,
        "timing": timing,
        "report": report,
        "preview": preview,
        "missed_transactions": missed_transactions,
        "clusters": cluster_stats(rows),
    }


def _persist_p2_run(
    run_id: str,
    family: str,
    n: int,
    seed: int,
    intensity: str,
    metrics: dict[str, Any],
    report: str,
    detections: list[dict[str, Any]],
) -> None:
    from app.core.db import session
    from app.data.schema import PaymentRow, SimulationRun

    db = session()
    try:
        db.add(
            SimulationRun(
                id=run_id,
                attack_family=family,
                n=n,
                seed=seed,
                intensity=intensity,
                report_text=report,
                metrics_json=json.dumps(metrics, default=str),
            )
        )
        for rec in detections[:500]:
            db.add(
                PaymentRow(
                    run_id=run_id,
                    transaction_id=str(rec.get("transaction_id")),
                    attack_family=family,
                    amount=float(rec.get("amount") or 0),
                    fraud_probability=float(rec.get("fraud_probability") or 0),
                    decision=str(rec.get("action") or rec.get("decision") or ""),
                    payload=json.dumps(rec, default=str),
                )
            )
        db.commit()
    except Exception:  # noqa: BLE001
        db.rollback()
    finally:
        db.close()


def dashboard() -> dict[str, Any]:
    st = store.get_state()
    dets = store.detections()
    metrics = st.get("metrics")
    if not dets or not metrics:
        return {"data_available": False, "reason": "No Blue Team stream yet. Run a Red Team simulation."}
    high = sum(1 for d in dets if int(d.get("risk_score") or 0) >= 80)
    return {
        "data_available": True,
        "simulation_id": st.get("simulation_id"),
        "model_id": st.get("model_id") or FRAUD_MODEL_ID,
        "transactions": len(dets),
        "threats": sum(1 for d in dets if float(d.get("fraud_probability") or 0) >= 0.5),
        "detection_rate": float(metrics.get("detection_rate") or metrics.get("recall") or 0),
        "precision": float(metrics.get("precision") or 0),
        "recall": float(metrics.get("recall") or 0),
        "f1": float(metrics.get("f1") or 0),
        "pr_auc": float(metrics.get("pr_auc") or 0),
        "fpr": float(metrics.get("fpr") or 0),
        "active_high_risk": high,
        "coverage": st.get("coverage") or {},
        "clusters": cluster_stats(store.frame()),
    }


def list_detections(
    attack: str | None = None,
    min_risk: int = 0,
    status: str | None = None,
) -> list[dict[str, Any]]:
    rows = []
    for d in store.detections():
        if attack and str(d.get("attack_prediction")) != attack and str(d.get("attack_family")) != attack:
            continue
        if int(d.get("risk_score") or 0) < min_risk:
            continue
        if status and str(d.get("action") or "").upper() != status.upper():
            continue
        rows.append(
            {
                "transaction_id": d.get("transaction_id"),
                "clock": d.get("clock") or _clock(d.get("timestamp")),
                "attack_prediction": d.get("attack_prediction"),
                "attack_family_label": d.get("attack_family"),
                "risk_score": d.get("risk_score"),
                "classification_confidence": d.get("classification_confidence"),
                "action": d.get("action"),
                "fraud_probability": d.get("fraud_probability"),
                "amount": d.get("amount"),
                "customer_id": d.get("customer_id"),
                "beneficiary_id": d.get("beneficiary_id"),
            }
        )
    return rows[:500]


def detection_detail(transaction_id: str) -> dict[str, Any]:
    for d in store.detections():
        if str(d.get("transaction_id")) == str(transaction_id):
            fired = [s for s in d.get("signals") or [] if s.get("fired")]
            return {
                "transaction_id": d.get("transaction_id"),
                "clock": d.get("clock") or _clock(d.get("timestamp")),
                "risk_score": d.get("risk_score"),
                "fraud_probability": d.get("fraud_probability"),
                "attack_classification": d.get("attack_prediction"),
                "classification_confidence": d.get("classification_confidence"),
                "signals": fired,
                "all_signals": d.get("signals"),
                "action": d.get("action"),
                "reason": d.get("reason"),
                "customer_id": d.get("customer_id"),
                "beneficiary_id": d.get("beneficiary_id"),
                "device_id": d.get("device_id"),
                "ip_id": d.get("ip_id"),
                "amount": d.get("amount"),
                "components": component_risks(pd.Series(d)),
            }
    raise KeyError(transaction_id)


def attack_coverage() -> dict[str, Any]:
    st = store.get_state()
    metrics = (st.get("p2_metrics") or {}).get("per_attack") or st.get("coverage") or {}
    dets = store.detections()
    dist: Counter[str] = Counter(str(d.get("attack_prediction") or "unknown") for d in dets)
    total = max(sum(dist.values()), 1)
    matrix = []
    for fam, block in (metrics.items() if isinstance(metrics, dict) else []):
        if not isinstance(block, dict):
            recall = float(block or 0)
            matrix.append({"family": fam, "generated": 0, "detected": 0, "missed": 0, "recall": recall})
            continue
        generated = int(block.get("generated") or 0)
        detected = int(block.get("detected") or 0)
        missed = int(block.get("missed") or max(generated - detected, 0))
        matrix.append(
            {
                "family": fam,
                "generated": generated,
                "detected": detected,
                "missed": missed,
                "recall": float(block.get("attack_recall") or block.get("recall") or 0),
            }
        )
    if not matrix and dets:
        fam = str(st.get("attack_family") or "unknown")
        generated = len(dets)
        detected = sum(1 for d in dets if float(d.get("fraud_probability") or 0) >= 0.5)
        matrix.append({"family": fam, "generated": generated, "detected": detected, "missed": generated - detected})
    return {
        "attacks_detected": sum(1 for d in dets if float(d.get("fraud_probability") or 0) >= 0.5),
        "distribution": {k: v / total for k, v in dist.items()},
        "recall_by_family": {
            k: float((v or {}).get("attack_recall") or (v or {}).get("recall") or v or 0) if isinstance(v, dict) else float(v or 0)
            for k, v in (metrics.items() if isinstance(metrics, dict) else [])
        },
        "matrix": matrix,
        "data_available": bool(dets or metrics),
    }


def network_view(entity_id: str | None = None) -> dict[str, Any]:
    df = store.frame()
    stats = cluster_stats(df)
    if df.empty:
        return {"data_available": False, "reason": "No Blue Team stream yet.", **{k: 0 for k in stats}}
    if not entity_id:
        if "beneficiary_id" in df.columns:
            entity_id = str(df["beneficiary_id"].mode().iloc[0])
        else:
            entity_id = str(df.iloc[0].get("customer_id"))
    graph = neighborhood(df, str(entity_id))
    profile = beneficiary_profile(df, str(entity_id))
    hits = [d for d in store.detections() if str(entity_id) in {str(d.get("beneficiary_id")), str(d.get("customer_id")), str(d.get("device_id")), str(d.get("ip_id"))}]
    if hits:
        fams = Counter(str(d.get("attack_prediction") or "unknown") for d in hits)
        top, n = fams.most_common(1)[0]
        profile["risk_score"] = max(int(d.get("risk_score") or 0) for d in hits)
        profile["classification"] = top
        profile["confidence"] = float(sum(float(d.get("classification_confidence") or 0) for d in hits if d.get("attack_prediction") == top) / max(n, 1))
        profile["signals"] = [s for s in (hits[0].get("signals") or []) if s.get("fired")]
    return {"data_available": True, **stats, "focus": graph, "profile": profile}


def entity_view(entity_type: str, entity_id: str) -> dict[str, Any]:
    df = store.frame()
    if df.empty:
        return {"found": False, "reason": "No Blue Team stream yet."}
    col = {
        "beneficiary": "beneficiary_id",
        "customer": "customer_id",
        "device": "device_id",
        "ip": "ip_id",
        "merchant": "merchant_id",
        "transaction": "transaction_id",
    }.get(entity_type, "beneficiary_id")
    if entity_type == "transaction":
        return detection_detail(entity_id)
    sub = df.loc[df[col].astype(str) == str(entity_id)] if col in df.columns else df.iloc[0:0]
    if sub.empty:
        return {"found": False, "entity_id": entity_id}
    return {
        "found": True,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "connected_accounts": int(sub["customer_id"].nunique()) if "customer_id" in sub.columns else 0,
        "devices": int(sub["device_id"].nunique()) if "device_id" in sub.columns else 0,
        "ips": int(sub["ip_id"].nunique()) if "ip_id" in sub.columns else 0,
        "transactions": int(len(sub)),
        "total_value": float(pd.to_numeric(sub["amount"], errors="coerce").fillna(0).sum()) if "amount" in sub.columns else 0.0,
        "graph": neighborhood(df, entity_id),
    }


def entity_timeline(entity_type: str, entity_id: str) -> list[dict[str, Any]]:
    df = store.frame()
    col = {
        "beneficiary": "beneficiary_id",
        "customer": "customer_id",
        "device": "device_id",
        "ip": "ip_id",
    }.get(entity_type, "beneficiary_id")
    if df.empty or col not in df.columns:
        return []
    sub = df.loc[df[col].astype(str) == str(entity_id)].sort_values("timestamp") if "timestamp" in df.columns else df
    out = []
    for _, row in sub.head(80).iterrows():
        out.append(
            {
                "timestamp": float(row.get("timestamp") or 0),
                "transaction_id": row.get("transaction_id"),
                "customer_id": row.get("customer_id"),
                "beneficiary_id": row.get("beneficiary_id"),
                "amount": float(row.get("amount") or 0),
            }
        )
    return out


def mitigation_queue() -> dict[str, Any]:
    dets = store.detections()
    buckets = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0}
    items = []
    for d in dets:
        r = int(d.get("risk_score") or 0)
        band = "Critical" if r >= 90 else "High" if r >= 75 else "Medium" if r >= 50 else "Low"
        buckets[band] += 1
        items.append(
            {
                "transaction_id": d.get("transaction_id"),
                "risk_score": r,
                "attack": d.get("attack_prediction"),
                "recommended": d.get("action"),
                "band": band,
                "beneficiary_id": d.get("beneficiary_id"),
                "customer_id": d.get("customer_id"),
            }
        )
    items.sort(key=lambda x: -int(x["risk_score"]))
    df = store.frame()
    cluster = None
    if not df.empty and "beneficiary_id" in df.columns:
        ben = str(df["beneficiary_id"].mode().iloc[0])
        sub = df.loc[df["beneficiary_id"].astype(str) == ben]
        cluster = {
            "beneficiary_id": ben,
            "accounts": int(sub["customer_id"].nunique()) if "customer_id" in sub.columns else 0,
            "devices": int(sub["device_id"].nunique()) if "device_id" in sub.columns else 0,
            "ips": int(sub["ip_id"].nunique()) if "ip_id" in sub.columns else 0,
            "recommended": "ISOLATE_CLUSTER",
        }
    return {"counts": buckets, "items": items[:200], "cluster": cluster}


def execute_mitigation(transaction_id: str, action: str, reason: str) -> dict[str, Any]:
    rec = store.apply_mitigation(transaction_id, action, reason)
    if rec.get("found") is False:
        raise KeyError(transaction_id)
    return rec


def isolate_cluster(reason: str = "Coordinated network isolated") -> dict[str, Any]:
    q = mitigation_queue()
    cluster = q.get("cluster")
    if not cluster:
        return {"applied": 0, "reason": "No cluster on the current stream."}
    ben = str(cluster.get("beneficiary_id") or "")
    applied = []
    for d in store.detections():
        if str(d.get("beneficiary_id")) == ben:
            applied.append(store.apply_mitigation(str(d.get("transaction_id")), "HOLD", reason))
    return {"applied": len(applied), "beneficiary_id": ben, "action": "HOLD", "cluster": cluster}


def defense_report(simulation_id: str | None = None) -> dict[str, Any]:
    st = store.get_state()
    if not st.get("report"):
        return {"data_available": False, "reason": "No defense report yet."}
    if simulation_id and st.get("simulation_id") != simulation_id:
        return {"data_available": False, "reason": "Unknown simulation_id."}
    return {
        "data_available": True,
        "simulation_id": st.get("simulation_id"),
        "report": st.get("report"),
        "payload": st.get("report_payload"),
        "timing": st.get("timing"),
    }


def current_model() -> dict[str, Any]:
    if _p2 is None and not (MODELS_DIR / "blue_fraud_0_2_0.joblib").exists():
        return {"data_available": False, "reason": "BLUE-FRAUD-0.2.0 is not trained yet."}
    team = p2_team()
    return {
        "data_available": True,
        "model_id": FRAUD_MODEL_ID,
        "classifier_id": CLS_MODEL_ID,
        "metrics": team.metrics,
        "feature_columns": list(team.feature_names),
    }


def model_compare() -> dict[str, Any]:
    if _p2 is None and not (MODELS_DIR / "blue_fraud_0_2_0.joblib").exists():
        return {"data_available": False, "reason": "BLUE-FRAUD-0.2.0 is not trained yet."}
    st = store.get_state()
    p2m = st.get("p2_metrics") or p2_team().metrics
    comparison = p2m.get("p0_comparison") or {}
    p2_hold = p2m.get("lightgbm") or {}
    from app.service import team as p0_team

    try:
        p0_hold = (p0_team().metrics or {}).get("lightgbm") or {}
    except Exception:  # noqa: BLE001
        p0_hold = {}
    families = {}
    for fam, block in comparison.items():
        if fam == "model_id" or not isinstance(block, dict):
            continue
        families[fam] = {
            "p0_recall": float((block.get("p0") or {}).get("recall") or 0),
            "p2_recall": float((block.get("p2") or {}).get("recall") or 0),
        }
    return {
        "data_available": True,
        "baseline": P0_MODEL_ID,
        "candidate": FRAUD_MODEL_ID,
        "holdout": {"p0": p0_hold, "p2": p2_hold},
        "coordinated_attacks": families,
        "classifier_id": CLS_MODEL_ID,
        "classifier_accuracy": p2m.get("classifier_accuracy"),
        "per_attack": p2m.get("per_attack") or {},
    }
