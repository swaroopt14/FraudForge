"""LOW / MEDIUM / HIGH / ADAPTIVE → mutation. HIGH is subtler (harder to detect)."""

from __future__ import annotations

from typing import Any

from app.threats.registry import ThreatRegistry
from app.threats.schema import MutationParams

LEVELS = ("LOW", "MEDIUM", "HIGH", "ADAPTIVE")


def lerp_mutation(low: MutationParams, high: MutationParams, t: float) -> MutationParams:
    t = min(1.0, max(0.0, float(t)))
    a, b = low.model_dump(), high.model_dump()
    out: dict[str, Any] = {}
    for key, va in a.items():
        vb = b[key]
        if isinstance(va, bool):
            out[key] = vb if t >= 0.5 else va
        elif isinstance(va, int) and key in {"fragment_parts", "cluster_count"}:
            out[key] = int(round(va + (vb - va) * t))
        elif isinstance(va, (int, float)):
            out[key] = type(va)(va + (vb - va) * t)
        else:
            out[key] = vb if t >= 0.5 else va
    return MutationParams.model_validate(out)


def adaptive_mutation(
    registry: ThreatRegistry,
    attack_id: str,
    variant_id: str | None,
    detection_rate: float,
) -> MutationParams:
    """High probe detection → blend toward HIGH (subtle). Low detection → stay nearer LOW."""
    low = registry.mutation(attack_id, "LOW", variant_id)
    high = registry.mutation(attack_id, "HIGH", variant_id)
    return lerp_mutation(low, high, float(detection_rate))


def resolve_mutation(
    registry: ThreatRegistry,
    attack_id: str,
    difficulty: str,
    variant_id: str | None = None,
    detection_rate: float | None = None,
) -> MutationParams:
    level = (difficulty or "MEDIUM").upper()
    if level == "ADAPTIVE":
        return adaptive_mutation(registry, attack_id, variant_id, 0.5 if detection_rate is None else detection_rate)
    if level not in ("LOW", "MEDIUM", "HIGH"):
        raise ValueError(f"unknown difficulty: {difficulty}")
    return registry.mutation(attack_id, level, variant_id)
