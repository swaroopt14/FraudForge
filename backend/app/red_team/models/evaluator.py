"""Asymmetric Red Team objective. Do not maximize attack success alone."""

from __future__ import annotations


def red_objective(
    *,
    success: float,
    fidelity: float,
    novelty: float,
    difficulty: float,
    diversity: float,
) -> float:
    return (
        0.25 * float(novelty)
        + 0.25 * float(fidelity)
        + 0.20 * float(difficulty)
        + 0.20 * float(success)
        + 0.10 * float(diversity)
    )


def red_metrics(payload: dict) -> dict[str, float]:
    metrics = payload.get("metrics") or {}
    fidelity = payload.get("fidelity") or {}
    return {
        "attack_success_rate": float(metrics.get("attack_success_rate") or payload.get("attack_success") or 0.0),
        "attack_fidelity": float(fidelity.get("overall_fidelity") or 0.0),
        "attack_novelty": float((payload.get("novelty") or {}).get("novelty_score") or 0.0) / 100.0,
        "attack_difficulty": {"LOW": 0.3, "MEDIUM": 0.65, "HIGH": 0.9, "ADAPTIVE": 0.75}.get(
            str(payload.get("difficulty") or "MEDIUM").upper(), 0.5
        ),
    }
