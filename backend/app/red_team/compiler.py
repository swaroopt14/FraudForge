"""Compile an accepted attack strategy into an AttackContract. Does not generate rows."""

from __future__ import annotations

from typing import Any

from app.redteam.contract import AttackContract
from app.redteam.difficulty import resolve_mutation
from app.threats.registry import get_registry


def compile_strategy(
    strategy: dict[str, Any],
    *,
    seed: int = 424242,
    transaction_count: int = 1000,
    target_population: str = "normal_customers",
) -> AttackContract:
    registry = get_registry()
    attack_id = str(strategy.get("attack_id") or strategy.get("attack_family") or "")
    threat = registry.get(attack_id)
    variant = registry.resolve_variant(threat.attack_id, strategy.get("variant_id"))
    difficulty = str(strategy.get("difficulty") or "medium").upper()
    mutation = resolve_mutation(registry, threat.attack_id, difficulty, variant.id)
    overlay = strategy.get("mutation_strategy") or {}
    if overlay:
        from app.threats.schema import MutationParams

        data = mutation.model_dump()
        if "beneficiary_change" in overlay:
            data["beneficiary_change_probability"] = float(overlay["beneficiary_change"])
        if "amount_deviation" in overlay:
            data["amount_deviation"] = float(overlay["amount_deviation"])
        if "device_change" in overlay:
            data["device_change_probability"] = float(overlay["device_change"])
        if "geo_deviation" in overlay:
            data["geo_deviation"] = float(overlay["geo_deviation"])
        mutation = MutationParams.model_validate(data)
    return AttackContract(
        attack_id=threat.attack_id,
        variant_id=variant.id,
        family=threat.family,
        difficulty=difficulty,
        seed=int(seed),
        transaction_count=int(transaction_count),
        target_population=target_population,
        mutation=mutation,
        detection_signals=list(threat.detection_signals),
    )
