"""Strict payment state machine. BLOCKED must never settle."""

from __future__ import annotations

ALLOWED_TRANSITIONS: dict[str, list[str]] = {
    "CREATED": ["INTENT_AUTHORIZED"],
    "INTENT_AUTHORIZED": ["AGENT_EXECUTING"],
    "AGENT_EXECUTING": ["PAYMENT_PREPARED"],
    "PAYMENT_PREPARED": ["RISK_SCORING"],
    "RISK_SCORING": ["BLOCKED", "STEP_UP", "REVIEW", "APPROVED"],
    "APPROVED": ["SETTLEMENT_SIMULATED"],
    "SETTLEMENT_SIMULATED": ["CASH_OUT_SIMULATED"],
    "BLOCKED": [],
    "STEP_UP": ["RISK_SCORING", "BLOCKED", "APPROVED"],
    "REVIEW": ["BLOCKED", "APPROVED"],
    "CASH_OUT_SIMULATED": [],
}


class InvalidTransition(ValueError):
    pass


class PaymentStateMachine:
    def __init__(self, initial: str = "CREATED") -> None:
        self.state = initial
        self.history: list[str] = [initial]

    def can(self, nxt: str) -> bool:
        return nxt in ALLOWED_TRANSITIONS.get(self.state, [])

    def transition(self, nxt: str) -> str:
        if not self.can(nxt):
            raise InvalidTransition(f"{self.state} → {nxt} is not allowed")
        self.state = nxt
        self.history.append(nxt)
        return self.state
