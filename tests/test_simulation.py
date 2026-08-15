"""Simulation engine, state machine, and intent policy tests."""

from __future__ import annotations

import pytest

from policy.decision import make_decision
from policy.intent_policy import evaluate_intent
from simulation.engine import PaymentSimulation, replay_before_after
from simulation.payment_state import InvalidTransition, PaymentStateMachine
from simulation.scenarios import list_scenarios, load_scenario


def test_state_machine_valid_and_blocked_cannot_settle() -> None:
    m = PaymentStateMachine()
    m.transition("INTENT_AUTHORIZED")
    m.transition("AGENT_EXECUTING")
    m.transition("PAYMENT_PREPARED")
    m.transition("RISK_SCORING")
    m.transition("BLOCKED")
    with pytest.raises(InvalidTransition):
        m.transition("SETTLEMENT_SIMULATED")
    with pytest.raises(InvalidTransition):
        m.transition("APPROVED")


def test_state_machine_approve_path() -> None:
    m = PaymentStateMachine()
    for nxt in [
        "INTENT_AUTHORIZED",
        "AGENT_EXECUTING",
        "PAYMENT_PREPARED",
        "RISK_SCORING",
        "APPROVED",
        "SETTLEMENT_SIMULATED",
        "CASH_OUT_SIMULATED",
    ]:
        m.transition(nxt)
    assert m.state == "CASH_OUT_SIMULATED"


def test_scenario_loads() -> None:
    row = load_scenario("agent_destination_substitution")
    assert row["expected_outcome"] == "BLOCK"
    assert row["entities"]["original_destination"] == "merchant_008"
    assert row["entities"]["malicious_destination"] == "beneficiary_991"


def test_intent_destination_blocks() -> None:
    intent = {
        "max_amount": 80000,
        "approved_destinations": ["merchant_008"],
        "allowed_categories": ["electronics"],
    }
    ok = evaluate_intent(intent, {"amount": 79500, "destination": "merchant_008", "category": "electronics"})
    assert ok["decision"] == "PASS"
    bad = evaluate_intent(
        intent,
        {
            "amount": 79500,
            "destination": "beneficiary_991",
            "category": "electronics",
            "beneficiary_is_new": True,
        },
    )
    assert bad["decision"] == "BLOCK"
    assert "destination_not_authorized" in bad["reason_codes"]
    over = evaluate_intent(intent, {"amount": 90000, "destination": "merchant_008", "category": "electronics"})
    assert over["decision"] == "BLOCK"
    cat = evaluate_intent(intent, {"amount": 100, "destination": "merchant_008", "category": "gambling"})
    assert cat["decision"] == "REVIEW"


def test_make_decision_intent_overrides_low_ml() -> None:
    intent = evaluate_intent(
        {"max_amount": 80000, "approved_destinations": ["merchant_008"]},
        {"amount": 79500, "destination": "beneficiary_991", "beneficiary_is_new": True},
    )
    full = make_decision(0.38, intent, 0.1, mode="full")
    assert full["decision"] == "BLOCK"
    weak = make_decision(0.38, intent, 0.1, mode="weak")
    assert weak["decision"] == "APPROVE"


def test_simulation_event_order_and_ground_truth() -> None:
    sim = PaymentSimulation("agent_destination_substitution", mode="full", persist=False, detect_fn=None)
    state = sim.run()
    stages = [e["stage"] for e in state["events"]]
    assert stages[0] == "reconnaissance"
    assert "agent_manipulation" in stages
    assert "authorization" in stages
    assert "intervention" in stages
    assert "settlement" in stages
    assert "learning" in stages
    assert state["events"][0]["ground_truth"]["label"] == "FRAUD"
    assert state["final_decision"]["decision"] == "BLOCK"
    assert state["payment_state"] == "BLOCKED"
    assert any(e["event_type"] == "payment_parameters_changed" for e in state["events"])
    changed = next(e for e in state["events"] if e["event_type"] == "payment_parameters_changed")
    assert changed["provenance"]["original_destination"] == "merchant_008"
    assert changed["provenance"]["new_destination"] == "beneficiary_991"
    settle = next(e for e in state["events"] if e["event_type"] == "settlement_simulated")
    assert settle["metadata"]["prevented"] is True
    assert settle["metadata"]["live_execution"] is False


def test_weak_then_full_replay() -> None:
    result = replay_before_after("agent_destination_substitution", detect_fn=None, persist=False)
    assert result["before"]["decision"] == "APPROVE"
    assert result["before"]["destination_substitution"] == "MISSED"
    assert result["after"]["decision"] == "BLOCK"
    assert result["after"]["destination_substitution"] == "DETECTED"
    assert result["improvement"]["new_signal"] == "intent-to-destination mismatch"
    assert result["evaluation"] == "SIMULATED EVALUATION"


def test_all_scenarios_load() -> None:
    rows = list_scenarios()
    assert len(rows) >= 4
    ids = {r["scenario_id"] for r in rows}
    assert "agent_destination_substitution" in ids
    assert "upi_qr_redirection" in ids


def test_qr_scenario_blocks_on_full() -> None:
    sim = PaymentSimulation("upi_qr_redirection", mode="full", persist=False, detect_fn=None)
    state = sim.run()
    assert state["final_decision"]["decision"] == "BLOCK"


def test_step_and_reset() -> None:
    sim = PaymentSimulation("agent_destination_substitution", mode="full", persist=False)
    first = sim.step()
    assert first["progress"]["done"] == 1
    sim.reset()
    assert sim.get_state()["progress"]["done"] == 0
    assert sim.get_state()["events"] == []
