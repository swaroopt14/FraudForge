"""Orchestration: ingest, train, simulate, score, report."""

from __future__ import annotations

import json
import uuid
from typing import Any

import pandas as pd

from app.core.config import ATTACK_FAMILIES, EVAL_DIR, MODELS_DIR, ensure_dirs
from app.core.db import session
from app.data.ingest import ingest, load_payments
from app.data.schema import PaymentRow, SimulationRun
from app.evaluation.fidelity import fidelity_report
from app.evaluation.report import FAMILY_COPY, render_report
from app.fraud.pipeline import BlueTeam, compute_metrics, feature_matrix
from app.risk.explain import explain_row
from app.risk.policy import decide
from app.simulation.attacks import generate_attacks, generate_mixed_attacks
from app.simulation.legit import fit_profiles, generate_legitimate

_team: BlueTeam | None = None
_payments: pd.DataFrame | None = None


def payments() -> pd.DataFrame:
    global _payments
    if _payments is None:
        _payments = load_payments()
    return _payments


def team() -> BlueTeam:
    global _team
    if _team is None:
        path = MODELS_DIR / "blue_team.joblib"
        if path.exists():
            _team = BlueTeam.load(path)
        else:
            _team = train_models()
    return _team


def feature_importance_payload() -> dict[str, Any]:
    blue = team()
    cached = blue.metrics.get("feature_importance")
    if (
        isinstance(cached, list)
        and cached
        and sum(1 for row in cached if float(row.get("importance", 0)) > 0) >= 3
    ):
        return {"features": cached, "source": blue.metrics.get("backend", "model")}
    sample = payments()
    n = min(800, len(sample))
    frame = sample.sample(n, random_state=0) if n else sample
    y = frame["fraud_label"].astype(int) if "fraud_label" in frame.columns else None
    x = feature_matrix(frame) if n else None
    pairs = blue.importance_pairs(x, y)
    features = [{"feature": name, "importance": float(value)} for name, value in pairs]
    blue.metrics["feature_importance"] = features
    return {"features": features, "source": blue.metrics.get("backend", "model")}


def train_models(sample_n: int | None = None) -> BlueTeam:
    global _team, _payments
    ensure_dirs()
    _payments = ingest(sample_n=sample_n)
    attacks = generate_mixed_attacks(_payments, n_each=400)
    from app.fraud.pipeline import prepare_split

    train, test = prepare_split(_payments, attacks)
    blue = BlueTeam()
    blue.train(train, test)
    per_attack = {}
    legit = test.loc[test["fraud_label"] == 0]
    for family in ATTACK_FAMILIES:
        atk = test.loc[test["attack_family"] == family]
        if atk.empty:
            atk = generate_attacks(_payments, family, 300, seed=7)
        mix = pd.concat([legit.sample(min(len(legit), 800), random_state=0), atk], ignore_index=True)
        proba = blue.score(mix)
        per_attack[family] = compute_metrics(mix["fraud_label"].to_numpy(), proba)
    blue.metrics["per_attack"] = per_attack
    profiles = fit_profiles(_payments)
    synth = generate_legitimate(profiles, 2000, seed=1)
    blue.metrics["fidelity"] = fidelity_report(_payments.loc[_payments["fraud_label"] == 0].head(5000), synth)
    blue.save()
    (EVAL_DIR / "per_attack.json").write_text(json.dumps(per_attack, indent=2))
    _team = blue
    return blue


def run_simulation(
    attack_id: str,
    transaction_count: int,
    seed: int,
    intensity: str = "medium",
) -> dict[str, Any]:
    ensure_dirs()
    source = payments()
    rows = generate_attacks(source, attack_id, transaction_count, seed=seed, intensity=intensity)
    family = rows["attack_family"].iloc[0]
    blue = team()
    proba = blue.score(rows)
    decisions = [decide(float(p)) for p in proba]
    y = rows["fraud_label"].to_numpy()
    attack_metrics = compute_metrics(y, proba)
    legit = source.loc[source["fraud_label"] == 0]
    if len(legit):
        hold = legit.sample(min(len(legit), max(500, transaction_count // 5)), random_state=seed)
        mix = pd.concat([rows, hold], ignore_index=True)
        metrics = compute_metrics(mix["fraud_label"].to_numpy(), blue.score(mix))
    else:
        metrics = dict(attack_metrics)
    metrics["detection_rate"] = attack_metrics["recall"]
    metrics["attack_recall"] = attack_metrics["recall"]
    missed_idx = [i for i, p in enumerate(proba) if int(y[i]) == 1 and float(p) < 0.5]
    run_id = uuid.uuid4().hex[:8]
    report = render_report(run_id, family, transaction_count, metrics)
    payload_rows = []
    for i, row in rows.reset_index(drop=True).iterrows():
        rec = row.to_dict()
        rec["fraud_probability"] = float(proba[i])
        rec["decision"] = decisions[i]
        rec["missed"] = i in missed_idx
        if i < 80 or i in missed_idx[:40]:
            rec["explanation"] = explain_row(blue.lgbm, pd.DataFrame([row]))
        payload_rows.append(rec)
    missed = [payload_rows[i] for i in missed_idx[:50]]
    db = session()
    try:
        db.add(
            SimulationRun(
                id=run_id,
                attack_family=family,
                n=transaction_count,
                seed=seed,
                intensity=intensity,
                report_text=report,
                metrics_json=json.dumps(metrics),
            )
        )
        for rec in payload_rows[:500]:
            db.add(
                PaymentRow(
                    run_id=run_id,
                    transaction_id=str(rec["transaction_id"]),
                    attack_family=family,
                    amount=float(rec["amount"]),
                    fraud_probability=float(rec["fraud_probability"]),
                    decision=str(rec["decision"]),
                    payload=json.dumps({k: rec[k] for k in rec if k != "explanation"}, default=str),
                )
            )
        db.commit()
    finally:
        db.close()
    return {
        "simulation_id": run_id,
        "attack_family": family,
        "generated": int(transaction_count),
        "detected": int(transaction_count - len(missed_idx)),
        "missed": int(len(missed_idx)),
        "detection_rate": float(metrics["recall"]),
        "metrics": metrics,
        "narrative": FAMILY_COPY.get(family, FAMILY_COPY["low_and_slow"]),
        "report": report,
        "missed_transactions": missed,
        "preview": payload_rows[:12],
    }


def score_transactions(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    df = pd.DataFrame(items)
    blue = team()
    proba = blue.score(df)
    out = []
    for i, row in df.reset_index(drop=True).iterrows():
        p = float(proba[i])
        out.append(
            {
                "transaction_id": str(row.get("transaction_id", i)),
                "fraud_probability": p,
                "decision": decide(p),
                "explanation": explain_row(blue.lgbm, pd.DataFrame([row])),
            }
        )
    return out


def get_simulation(run_id: str) -> dict[str, Any]:
    db = session()
    try:
        run = db.get(SimulationRun, run_id)
        if run is None:
            raise KeyError(run_id)
        rows = db.query(PaymentRow).filter(PaymentRow.run_id == run_id).limit(80).all()
        return {
            "simulation_id": run.id,
            "attack_family": run.attack_family,
            "n": run.n,
            "seed": run.seed,
            "intensity": run.intensity,
            "metrics": json.loads(run.metrics_json or "{}"),
            "report": run.report_text,
            "transactions": [
                {
                    "transaction_id": r.transaction_id,
                    "amount": r.amount,
                    "fraud_probability": r.fraud_probability,
                    "decision": r.decision,
                    **json.loads(r.payload or "{}"),
                }
                for r in rows
            ],
        }
    finally:
        db.close()


def get_transaction(tx_id: str) -> dict[str, Any]:
    db = session()
    try:
        row = db.query(PaymentRow).filter(PaymentRow.transaction_id == tx_id).first()
        if row is None:
            raise KeyError(tx_id)
        payload = json.loads(row.payload or "{}")
        payload.update(
            {
                "transaction_id": row.transaction_id,
                "fraud_probability": row.fraud_probability,
                "decision": row.decision,
                "attack_family": row.attack_family,
            }
        )
        return payload
    finally:
        db.close()
