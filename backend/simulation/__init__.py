"""Event-driven payment-attack simulator. Synthetic data only — no live rails."""

from .engine import PaymentSimulation, list_scenarios, load_scenario
from .events import EVENT_TYPES, STAGES, SimEvent
from .payment_state import ALLOWED_TRANSITIONS, InvalidTransition, PaymentStateMachine

__all__ = [
    "ALLOWED_TRANSITIONS",
    "EVENT_TYPES",
    "InvalidTransition",
    "PaymentSimulation",
    "PaymentStateMachine",
    "STAGES",
    "SimEvent",
    "list_scenarios",
    "load_scenario",
]
