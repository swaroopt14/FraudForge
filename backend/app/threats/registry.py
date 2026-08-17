"""In-memory threat registry."""

from __future__ import annotations

from pathlib import Path

from app.threats.loader import load_threats
from app.threats.schema import MutationParams, ThreatDefinition, ThreatVariant


class ThreatRegistry:
    def __init__(self, threats: list[ThreatDefinition] | None = None, directory: Path | None = None) -> None:
        self._threats = {t.attack_id: t for t in (threats if threats is not None else load_threats(directory))}

    def get(self, attack_id: str) -> ThreatDefinition:
        if attack_id in self._threats:
            return self._threats[attack_id]
        for threat in self._threats.values():
            if threat.family == attack_id or attack_id in {v.id for v in threat.variants}:
                return threat
        raise KeyError(attack_id)

    def list(self) -> list[ThreatDefinition]:
        return list(self._threats.values())

    def attack_ids(self) -> list[str]:
        return list(self._threats)

    def all_variants(self) -> list[tuple[ThreatDefinition, ThreatVariant]]:
        out = []
        for threat in self._threats.values():
            for variant in threat.variants:
                out.append((threat, variant))
        return out

    def variant_count(self) -> int:
        return len(self.all_variants())

    def resolve_variant(self, attack_id: str, variant_id: str | None) -> ThreatVariant:
        threat = self.get(attack_id)
        if variant_id:
            for variant in threat.variants:
                if variant.id == variant_id:
                    return variant
            raise KeyError(variant_id)
        return threat.variants[0]

    def mutation(self, attack_id: str, difficulty: str, variant_id: str | None = None) -> MutationParams:
        threat = self.get(attack_id)
        base = threat.difficulty_levels[difficulty.upper()]
        variant = self.resolve_variant(attack_id, variant_id)
        return base.merged(variant.overlays)


_REGISTRY: ThreatRegistry | None = None


def get_registry() -> ThreatRegistry:
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = ThreatRegistry()
    return _REGISTRY
