"""Hybrid blue-team layers: rules + ML + graph + intent."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from features import ensure_narrative


def _col(df: pd.DataFrame, name: str, default: float = 0.0) -> np.ndarray:
    if name not in df.columns:
        return np.full(len(df), default, dtype=float)
    return pd.to_numeric(df[name], errors="coerce").fillna(default).to_numpy(dtype=float)


def rules_score(df: pd.DataFrame) -> np.ndarray:
    """Deterministic behavioral rules. Score only — does not BLOCK alone."""
    vel = _col(df, "velocity_1h")
    device = _col(df, "device_new")
    loc = _col(df, "location_mismatch")
    bene = _col(df, "beneficiary_name_match", 1.0)
    mule = _col(df, "mule_account_risk")
    score = np.zeros(len(df), dtype=float)
    score += np.clip((vel - 3.0) / 8.0, 0.0, 1.0) * 0.28
    score += np.clip(device * loc, 0.0, 1.0) * 0.22
    score += np.clip((1.0 - bene) * np.clip(mule, 0.0, 1.0), 0.0, 1.0) * 0.25
    kyc = _col(df, "kyc_liveness_risk")
    doc = _col(df, "document_tamper_score")
    bio = _col(df, "biometric_mismatch")
    voice = _col(df, "voiceprint_mismatch")
    score += np.clip(0.35 * kyc + 0.30 * doc + 0.20 * bio + 0.15 * voice, 0.0, 1.0) * 0.25
    return np.clip(score, 0.0, 1.0)


def intent_score(df: pd.DataFrame) -> np.ndarray:
    """Agent Pay / delegation mismatch. 1.0 is a hard BLOCK candidate."""
    violation = _col(df, "constraint_violation")
    ratio = _col(df, "amount_vs_limit_ratio")
    over = (ratio > 1.0).astype(float)
    return np.clip(np.maximum(violation, over), 0.0, 1.0)


def blend_layers(
    ml: np.ndarray,
    graph: np.ndarray,
    rules: np.ndarray,
    intent: np.ndarray,
) -> np.ndarray:
    return np.clip(0.50 * ml + 0.20 * graph + 0.15 * rules + 0.15 * intent, 0.0, 1.0)


# Research intelligence stack (display). BLOCK still uses tree OR intent.
INTELLIGENCE_LAYERS: dict[str, dict[str, Any]] = {
    "V0": {"label": "Transaction", "weights": {"ml": 1.0}},
    "V1": {"label": "Behavioral", "weights": {"ml": 0.70, "rules": 0.30}},
    "V4": {"label": "Intent", "weights": {"ml": 0.55, "rules": 0.15, "intent": 0.30}},
    "V5": {"label": "Agent", "weights": {"ml": 0.50, "graph": 0.20, "rules": 0.15, "intent": 0.15}},
}


def score_intelligence_layer(layers: dict[str, Any], layer: str, index: int = 0) -> float:
    spec = INTELLIGENCE_LAYERS.get(layer) or INTELLIGENCE_LAYERS["V5"]
    total = 0.0
    for key, weight in spec["weights"].items():
        values = layers.get(key) or [0.0]
        total += float(weight) * float(values[index] if index < len(values) else 0.0)
    return float(np.clip(total, 0.0, 1.0))


def score_hybrid(
    df: pd.DataFrame,
    ml_proba: np.ndarray,
    graph_scores: np.ndarray,
    threshold: float,
) -> dict[str, Any]:
    work = ensure_narrative(df)
    ml = np.asarray(ml_proba, dtype=float)
    graph = np.asarray(graph_scores, dtype=float)
    if len(graph) != len(ml):
        graph = np.resize(graph, len(ml))
    rules = rules_score(work)
    intent = intent_score(work)
    hybrid = blend_layers(ml, graph, rules, intent)
    tree_block = ml >= float(threshold)
    intent_block = intent >= 0.99
    block = tree_block | intent_block
    return {
        "rules": rules.tolist(),
        "ml": ml.tolist(),
        "graph": graph.tolist(),
        "intent": intent.tolist(),
        "hybrid": hybrid.tolist(),
        "tree_block": tree_block.astype(int).tolist(),
        "intent_block": intent_block.astype(int).tolist(),
        "block": block.astype(int).tolist(),
        "decision": ["BLOCK" if b else "APPROVE" for b in block],
    }


__all__ = [
    "INTELLIGENCE_LAYERS",
    "blend_layers",
    "intent_score",
    "rules_score",
    "score_hybrid",
    "score_intelligence_layer",
]
