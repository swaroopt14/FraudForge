"""Asymmetric evaluation: Red generation quality vs Blue detection quality."""

from __future__ import annotations

from typing import Any

from app.fraud.pipeline import compute_metrics
from app.red_team.models.evaluator import red_metrics, red_objective


def blue_metrics(y_true, proba, threshold: float = 0.5) -> dict[str, Any]:
    return compute_metrics(y_true, proba, threshold=threshold)


def red_scorecard(payload: dict[str, Any]) -> dict[str, Any]:
    parts = red_metrics(payload)
    return {
        **parts,
        "objective": red_objective(
            success=parts["attack_success_rate"],
            fidelity=parts["attack_fidelity"],
            novelty=parts["attack_novelty"],
            difficulty=parts["attack_difficulty"],
            diversity=1.0,
        ),
        "note": "Red is not scored with PR-AUC. Blue is not scored with novelty.",
    }
