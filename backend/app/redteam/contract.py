"""Attack contract — what the simulator must execute."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.threats.schema import MutationParams


class AttackContract(BaseModel):
    attack_id: str
    variant_id: str
    family: str
    difficulty: str
    seed: int
    transaction_count: int = Field(ge=1)
    target_population: str = "normal_customers"
    mutation: MutationParams
    detection_signals: list[str] = Field(default_factory=list)
    ground_truth_label: int = 1

    def fingerprint(self) -> dict[str, Any]:
        return {
            "attack_id": self.attack_id,
            "variant_id": self.variant_id,
            "difficulty": self.difficulty,
            "seed": self.seed,
            "transaction_count": self.transaction_count,
            "target_population": self.target_population,
            "mutation": self.mutation.model_dump(),
        }
