"""Final decision: intent is hard BLOCK; ML and anomaly are configurable."""

from __future__ import annotations

from typing import Any

DEFAULT_THRESHOLDS = {
    "ml_block": 0.85,
    "anomaly_block": 0.90,
    "review": 0.50,
}


def make_decision(
    model_score: float,
    intent_result: dict[str, Any],
    anomaly_score: float = 0.0,
    thresholds: dict[str, float] | None = None,
    mode: str = "full",
) -> dict[str, Any]:
    thr = {**DEFAULT_THRESHOLDS, **(thresholds or {})}
    reasons: list[str] = list(intent_result.get("reason_codes") or [])
    intent_decision = str(intent_result.get("decision") or "PASS")

    if mode == "weak":
        # Amount-only: if intent amount passed, approve even when destination changed.
        if "amount_over_authorized_limit" in reasons:
            return {
                "decision": "BLOCK",
                "reason_codes": ["amount_over_authorized_limit"],
                "mode": mode,
                "model_score": model_score,
                "intent_score": float(intent_result.get("score") or 0),
                "anomaly_score": anomaly_score,
            }
        return {
            "decision": "APPROVE",
            "reason_codes": ["amount_within_limit_only"],
            "mode": mode,
            "model_score": model_score,
            "intent_score": float(intent_result.get("score") or 0),
            "anomaly_score": anomaly_score,
        }

    if intent_decision == "BLOCK":
        return {
            "decision": "BLOCK",
            "reason_codes": reasons or ["intent_block"],
            "mode": mode,
            "model_score": model_score,
            "intent_score": float(intent_result.get("score") or 0),
            "anomaly_score": anomaly_score,
        }
    if model_score >= thr["ml_block"]:
        reasons = reasons + ["ml_score_block"]
        return {
            "decision": "BLOCK",
            "reason_codes": reasons,
            "mode": mode,
            "model_score": model_score,
            "intent_score": float(intent_result.get("score") or 0),
            "anomaly_score": anomaly_score,
        }
    if anomaly_score >= thr["anomaly_block"]:
        reasons = reasons + ["anomaly_block"]
        return {
            "decision": "BLOCK",
            "reason_codes": reasons,
            "mode": mode,
            "model_score": model_score,
            "intent_score": float(intent_result.get("score") or 0),
            "anomaly_score": anomaly_score,
        }
    if intent_decision == "REVIEW" or model_score >= thr["review"]:
        return {
            "decision": "REVIEW",
            "reason_codes": reasons or ["medium_risk"],
            "mode": mode,
            "model_score": model_score,
            "intent_score": float(intent_result.get("score") or 0),
            "anomaly_score": anomaly_score,
        }
    return {
        "decision": "APPROVE",
        "reason_codes": [],
        "mode": mode,
        "model_score": model_score,
        "intent_score": float(intent_result.get("score") or 0),
        "anomaly_score": anomaly_score,
    }
