"""P1 threat schema — executable definitions, not prose."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator


class MutationParams(BaseModel):
    amount_deviation: float = 0.0
    velocity_multiplier: float = 1.0
    merchant_count_multiplier: float = 1.0
    geo_deviation: float = 0.0
    distance_boost: float = 0.0
    device_change_probability: float = 0.0
    ip_change_probability: float = 0.0
    beneficiary_change_probability: float = 0.0
    merchant_change_probability: float = 0.0
    failed_auth_boost: float = 0.0
    hour_shift: float = 0.0
    dest_concentration_delta: float = 0.0
    account_age_scale: float = 1.0
    share_device: bool = False
    share_ip: bool = False
    share_merchant: bool = False
    share_beneficiary: bool = False
    fragment_parts: int = 1
    category_flip: bool = False
    cluster_count: int = 1
    spread_seconds: float = 0.0

    def merged(self, overlay: dict[str, Any] | None) -> "MutationParams":
        if not overlay:
            return self.model_copy()
        data = self.model_dump()
        data.update({k: v for k, v in overlay.items() if v is not None})
        return MutationParams.model_validate(data)


class ThreatVariant(BaseModel):
    id: str
    name: str
    overlays: dict[str, Any] = Field(default_factory=dict)


class ThreatDefinition(BaseModel):
    attack_id: str
    name: str
    category: str
    evidence_level: str
    objective: str
    target: str
    attack_surface: list[str]
    required_entities: list[str]
    required_features: list[str]
    mutation_strategy: str
    network_strategy: str = "none"
    intent_strategy: str = "none"
    agent_strategy: str = "none"
    evasion_strategies: list[str] = Field(default_factory=list)
    difficulty_levels: dict[str, MutationParams]
    simulation_template: str
    detection_signals: list[str]
    expected_mitigation: str
    family: str
    variants: list[ThreatVariant]

    @field_validator("attack_id")
    @classmethod
    def _id(cls, value: str) -> str:
        if "-" not in value or len(value) < 5:
            raise ValueError("attack_id must look like ATO-001")
        return value

    @field_validator("difficulty_levels")
    @classmethod
    def _levels(cls, value: dict[str, MutationParams]) -> dict[str, MutationParams]:
        needed = {"LOW", "MEDIUM", "HIGH"}
        keys = {k.upper() for k in value}
        if not needed.issubset(keys):
            raise ValueError("difficulty_levels must include LOW, MEDIUM, HIGH")
        return {k.upper(): v for k, v in value.items()}

    @field_validator("variants")
    @classmethod
    def _variants(cls, value: list[ThreatVariant]) -> list[ThreatVariant]:
        if len(value) < 5:
            raise ValueError("each threat needs at least 5 variants")
        ids = [v.id for v in value]
        if len(ids) != len(set(ids)):
            raise ValueError("variant ids must be unique")
        return value
