"""Deterministic P2 risk + evidence + mitigation. Not an extra ML model."""

from __future__ import annotations

from typing import Any

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
