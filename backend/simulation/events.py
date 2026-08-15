"""Simulation event envelope. Every stage emits one or more events."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

STAGES = [
    "reconnaissance",
    "social_engineering",
    "identity_compromise",
    "agent_manipulation",
    "payment_preparation",
    "payment_initiation",
    "authorization",
    "intervention",
    "settlement",
    "learning",
]

EVENT_TYPES = [
    "profile_observed",
    "message_generated",
    "login_attempt",
    "device_registered",
    "intent_created",
    "tool_called",
    "tool_output_received",
    "payment_parameters_changed",
    "payment_requested",
    "risk_scored",
    "policy_checked",
    "payment_blocked",
    "payment_approved",
    "payment_reviewed",
    "settlement_simulated",
    "cash_out_simulated",
    "hard_negative_created",
    "model_retrained",
]


@dataclass
class SimEvent:
    event_id: str
    simulation_id: str
    scenario_id: str
    sequence: int
    timestamp: str
    stage: str
    event_type: str
    actor_type: str
    actor_id: str
    customer_id: str | None = None
    device_id: str | None = None
    merchant_id: str | None = None
    amount: float | None = None
    currency: str | None = "INR"
    payment_rail: str | None = None
    status: str = "emitted"
    risk_signals: dict[str, Any] = field(default_factory=dict)
    provenance: dict[str, Any] = field(default_factory=dict)
    ground_truth: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    decision: str | None = None
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def clock_label(seconds: int) -> str:
    hours, rem = divmod(int(seconds), 3600)
    minutes, secs = divmod(rem, 60)
    return f"{12 + hours:02d}:{minutes:02d}:{secs:02d}"
