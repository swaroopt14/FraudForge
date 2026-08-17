"""Fraud taxonomy as a common language: threat → family → variant → difficulty → params → signals."""

from __future__ import annotations

from typing import Any

from app.threats.registry import get_registry


def taxonomy_payload() -> dict[str, Any]:
    registry = get_registry()
    families = []
    for threat in registry.list():
        families.append(
            {
                "attack_id": threat.attack_id,
                "name": threat.name,
                "family": threat.family,
                "category": threat.category,
                "variants": [{"id": v.id, "name": v.name, "overlays": v.overlays} for v in threat.variants],
                "difficulty": {
                    key: params.model_dump() for key, params in threat.difficulty_levels.items()
                },
                "simulation_parameters": {
                    key: params.model_dump() for key, params in threat.difficulty_levels.items()
                },
                "observable_signals": list(threat.detection_signals),
                "mutation_strategy": threat.mutation_strategy,
                "network_strategy": threat.network_strategy,
                "intent_strategy": threat.intent_strategy,
                "agent_strategy": threat.agent_strategy,
            }
        )
    return {
        "phase": "P1",
        "n_families": len(families),
        "n_variants": registry.variant_count(),
        "chain": ["threat", "family", "variant", "difficulty", "simulation_parameters", "observable_signals"],
        "families": families,
        "red_objective": "maximize attack fidelity and coverage of realistic fraud behavior",
        "blue_objective": "maximize attack identification diversity and detection efficacy",
    }
