"""Deterministic P2 risk + evidence + mitigation. Not an extra ML model."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from app.blue_team.features import beneficiary_risk, device_risk, geo_risk, ip_risk, network_risk
from app.risk.policy import decide


def component_risks(row: pd.Series) -> dict[str, float]:
    return {
        "transaction_risk": float(row.get("fraud_probability") or 0.0),
        "geo_risk": geo_risk(row),
        "device_risk": device_risk(row),
        "ip_risk": ip_risk(row),
        "beneficiary_risk": beneficiary_risk(row),
        "network_risk": network_risk(row),
    }


def risk_score(row: pd.Series) -> int:
    c = component_risks(row)
    raw = (
        0.40 * c["transaction_risk"]
        + 0.20 * c["network_risk"]
        + 0.15 * c["geo_risk"]
        + 0.10 * c["device_risk"]
        + 0.15 * c["beneficiary_risk"]
    )
    return int(round(100.0 * min(1.0, max(0.0, raw))))


def evidence_signals(row: pd.Series) -> list[dict[str, Any]]:
    checks = [
        ("Beneficiary fan-in", float(row.get("beneficiary_fan_in") or 0.0) >= 8.0, "HIGH"),
        ("Shared device", float(row.get("device_is_shared") or 0.0) >= 1.0, "HIGH"),
        ("Shared IP", float(row.get("ip_is_shared") or 0.0) >= 1.0, "MEDIUM"),
        ("Impossible travel", float(row.get("geo_impossible_travel") or 0.0) >= 1.0, "HIGH"),
        ("Abnormal transaction sequence", float(row.get("geo_impossible_travel") or 0.0) >= 1.0 or float(row.get("transaction_count_1h") or 0.0) >= 4.0, "MEDIUM"),
        ("Account relationship anomaly", float(row.get("network_degree") or 0.0) >= 1.2, "MEDIUM"),
        ("Transaction concentration", float(row.get("beneficiary_customer_share") or 0.0) >= 0.15, "MEDIUM"),
        ("Network degree", float(row.get("network_degree") or 0.0) >= 1.2, "MEDIUM"),
        ("Amount deviation", abs(float(row.get("amount_deviation") or 0.0)) >= 2.0, "LOW"),
        ("Failed auth", float(row.get("failed_auth_count") or 0.0) >= 1.0, "HIGH"),
    ]
    return [{"signal": name, "fired": fired, "severity": sev} for name, fired, sev in checks]


def recommend_action(row: pd.Series, fraud_probability: float) -> str:
    net = network_risk(row)
    geo = geo_risk(row)
    if net >= 0.7 or fraud_probability >= 0.80:
        return "BLOCK"
    if net >= 0.55:
        return "HOLD"
    if net >= 0.45 or geo >= 0.7 or fraud_probability >= 0.60:
        return "REVIEW"
    if fraud_probability >= 0.30:
        return "STEP_UP"
    policy = decide(fraud_probability)
    return policy if policy != "STEP_UP" else "STEP_UP"


def mitigation_reason(family: str, signals: list[dict[str, Any]]) -> str:
    fired = [s["signal"] for s in signals if s["fired"]]
    if family == "mule_network" or "Beneficiary fan-in" in fired:
        return "Multiple accounts exhibit coordinated payment behavior around the same beneficiary."
    if "Impossible travel" in fired:
        return "Same account appears in distant geographies inside an impossible travel window."
    if "Shared device" in fired:
        return "One device is used across many otherwise unrelated accounts."
    if "Shared IP" in fired:
        return "One IP is used across many otherwise unrelated accounts."
    if fired:
        return "Contextual signals fire together on this payment."
    return "Score is elevated relative to the calibrated detector."


def combine(fraud_probability: float) -> dict[str, Any]:
    p = float(fraud_probability)
    return {
        "transaction": {"enabled": True, "value": p, "phase": "P0"},
        "behavior": {"enabled": True, "value": p, "phase": "P0", "note": "velocity/amount/device already inside BLUE-0.1.0"},
        "network": {"enabled": False, "value": None, "phase": "P2"},
        "geo": {"enabled": False, "value": None, "phase": "P2"},
        "intent": {"enabled": False, "value": None, "phase": "P3"},
        "agent": {"enabled": False, "value": None, "phase": "P3"},
        "risk_score": int(round(min(1.0, max(0.0, p)) * 100)),
        "decision": decide(p),
        "mitigation": {"action": decide(p), "reason": "policy on fraud_probability; network/geo/intent/agent not enabled"},
    }


def decide_v011(risk_score: int) -> str:
    score = int(risk_score)
    if score < 30:
        return "ALLOW"
    if score < 60:
        return "MONITOR"
    if score < 80:
        return "STEP_UP"
    if score < 90:
        return "REVIEW"
    return "BLOCK"


def combine_calibrated(calibrated_probability: float, raw_probability: float | None = None) -> dict[str, Any]:
    p = float(calibrated_probability)
    risk = int(round(min(1.0, max(0.0, p)) * 100))
    action = decide_v011(risk)
    raw = None if raw_probability is None else float(raw_probability)
    return {
        "transaction": {"enabled": True, "value": p, "phase": "P1", "raw": raw},
        "behavior": {"enabled": True, "value": p, "phase": "P1", "note": "temporal/behavioral features in BLUE-0.1.1"},
        "network": {"enabled": False, "value": None, "phase": "P2"},
        "geo": {"enabled": False, "value": None, "phase": "P2"},
        "intent": {"enabled": False, "value": None, "phase": "P3"},
        "agent": {"enabled": False, "value": None, "phase": "P3"},
        "risk_score": risk,
        "decision": action,
        "policy": "BLUE-0.1.1",
        "bands": {"ALLOW": "0-29", "MONITOR": "30-59", "STEP_UP": "60-79", "REVIEW": "80-89", "BLOCK": "90-100"},
        "mitigation": {
            "action": action,
            "reason": "calibrated risk 0–100; network/geo/intent/agent not enabled",
        },
    }


def combine_p2(
    fraud_probability: float,
    network_risk: float | None = None,
    geo_risk: float | None = None,
    raw_probability: float | None = None,
) -> dict[str, Any]:
    p = float(fraud_probability)
    n = 0.0 if network_risk is None else float(np.clip(network_risk, 0.0, 1.0))
    g = 0.0 if geo_risk is None else float(np.clip(geo_risk, 0.0, 1.0))
    blended = float(np.clip(0.70 * p + 0.20 * n + 0.10 * g, 0.0, 1.0))
    risk = int(round(blended * 100))
    action = decide_v011(risk)
    raw = None if raw_probability is None else float(raw_probability)
    return {
        "transaction": {"enabled": True, "value": p, "phase": "P1", "raw": raw},
        "behavior": {"enabled": True, "value": p, "phase": "P1", "note": "P1 features plus P2 graph scores in BLUE-0.2.0"},
        "network": {"enabled": True, "value": n, "phase": "P2"},
        "geo": {"enabled": True, "value": g, "phase": "P2"},
        "intent": {"enabled": False, "value": None, "phase": "P3"},
        "agent": {"enabled": False, "value": None, "phase": "P3"},
        "risk_score": risk,
        "decision": action,
        "policy": "BLUE-0.2.0",
        "bands": {"ALLOW": "0-29", "MONITOR": "30-59", "STEP_UP": "60-79", "REVIEW": "80-89", "BLOCK": "90-100"},
        "mitigation": {
            "action": action,
            "reason": "calibrated fraud probability plus explainable network/geo risk; intent/agent not enabled",
        },
    }
