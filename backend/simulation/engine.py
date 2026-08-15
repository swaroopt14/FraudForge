"""Stepwise payment simulation. Synthetic IDs and simulated time only."""

from __future__ import annotations

import uuid
from typing import Any, Callable

from policy.decision import make_decision
from policy.intent_policy import evaluate_intent
from simulation.events import STAGES, SimEvent, clock_label
from simulation.payment_state import PaymentStateMachine
from simulation.scenarios import list_scenarios, load_scenario
from storage.event_store import append_event, append_failure, append_hard_negative, load_registry, register_version

DetectFn = Callable[[dict[str, Any]], dict[str, Any]]


def _eid() -> str:
    return f"evt_{uuid.uuid4().hex[:8]}"


class PaymentSimulation:
    def __init__(
        self,
        scenario_id: str = "agent_destination_substitution",
        *,
        seed: int = 42,
        mode: str = "full",
        detect_fn: DetectFn | None = None,
        persist: bool = True,
        payment_rail: str | None = None,
    ) -> None:
        self.scenario = load_scenario(scenario_id)
        self.seed = seed
        self.mode = mode if mode in {"full", "weak"} else "full"
        self.detect_fn = detect_fn
        self.persist = persist
        self.simulation_id = f"sim_{uuid.uuid4().hex[:6]}"
        self.machine = PaymentStateMachine()
        self.events: list[SimEvent] = []
        self.clock = 0
        self.cursor = 0
        self.detect_result: dict[str, Any] | None = None
        self.intent_result: dict[str, Any] | None = None
        self.final_decision: dict[str, Any] | None = None
        self.failure_artifact: dict[str, Any] | None = None
        self.learning: dict[str, Any] | None = None
        self.risk_series: list[dict[str, Any]] = []
        rail = payment_rail or self.scenario.get("payment_rail") or "card"
        self.payment_rail = rail
        self._plan = self._build_plan()

    def _entities(self) -> dict[str, Any]:
        return dict(self.scenario.get("entities") or {})

    def _payment(self) -> dict[str, Any]:
        pay = dict(self.scenario.get("payment") or {})
        ent = self._entities()
        dest = ent.get("malicious_destination") or ent.get("original_destination")
        return {
            "amount": float(pay.get("amount") or 0),
            "tabular_amount": float(pay.get("tabular_amount") or pay.get("amount") or 0),
            "currency": pay.get("currency") or "INR",
            "category": pay.get("category") or "electronics",
            "destination": dest,
            "original_destination": ent.get("original_destination"),
            "beneficiary_is_new": dest != ent.get("original_destination"),
        }

    def _overlay_row(self) -> dict[str, Any]:
        pay = self._payment()
        family = self.scenario.get("attack_family") or "prompt_injection_pay"
        dest_swap = pay["beneficiary_is_new"]
        return {
            "Amount": pay["tabular_amount"],
            "Time": 43200.0,
            "attack_family": family if family != "mule_network" else "prompt_injection_pay",
            "Class": 1,
            "device_new": 0,
            "velocity_1h": 3 if dest_swap else 8,
            "location_mismatch": 0,
            "beneficiary_name_match": 0 if dest_swap else 1,
            "mule_account_risk": 0.72 if dest_swap else 0.18,
            "constraint_violation": 1 if dest_swap else 0,
            "amount_vs_limit_ratio": min(pay["amount"] / max(float((self.scenario.get("intent") or {}).get("max_amount") or 1), 1.0), 1.5),
            "hour_of_day": 12.1,
        }

    def emit(
        self,
        stage: str,
        event_type: str,
        summary: str,
        *,
        payload: dict[str, Any] | None = None,
        risk_signals: dict[str, Any] | None = None,
        provenance: dict[str, Any] | None = None,
        decision: str | None = None,
        actor_type: str = "system",
        actor_id: str = "sim",
        advance: int = 6,
        status: str = "emitted",
    ) -> SimEvent:
        self.clock += max(0, advance)
        if self.clock == 0 and not self.events:
            pass
        ent = self._entities()
        pay = self._payment()
        event = SimEvent(
            event_id=_eid(),
            simulation_id=self.simulation_id,
            scenario_id=self.scenario["scenario_id"],
            sequence=len(self.events) + 1,
            timestamp=clock_label(self.clock),
            stage=stage,
            event_type=event_type,
            actor_type=actor_type,
            actor_id=actor_id,
            customer_id=ent.get("customer_id"),
            device_id=ent.get("device_id"),
            merchant_id=ent.get("merchant_id"),
            amount=pay["amount"],
            currency=pay["currency"],
            payment_rail=self.payment_rail,
            status=status,
            risk_signals=risk_signals or {},
            provenance=provenance or {},
            ground_truth={
                "label": (self.scenario.get("red_team") or {}).get("ground_truth", "FRAUD"),
                "expected_outcome": self.scenario.get("expected_outcome"),
            },
            metadata=payload or {},
            decision=decision,
            summary=summary,
        )
        self.events.append(event)
        self._record_risk(event)
        if self.persist:
            append_event(event.to_dict())
        return event

    def _record_risk(self, event: SimEvent) -> None:
        prev = self.risk_series[-1] if self.risk_series else {
            "sequence": 0,
            "timestamp": "12:00:00",
            "transaction": 0.05,
            "device": 0.04,
            "graph": 0.06,
            "intent": 0.02,
            "anomaly": 0.03,
        }
        bump = {
            "reconnaissance": {"transaction": 0.02},
            "social_engineering": {"transaction": 0.05},
            "identity_compromise": {"device": 0.08},
            "agent_manipulation": {"intent": 0.25, "anomaly": 0.12},
            "payment_preparation": {"intent": 0.35, "graph": 0.18, "transaction": 0.10},
            "payment_initiation": {"transaction": 0.12, "graph": 0.10},
            "authorization": {},
            "intervention": {},
            "settlement": {},
            "learning": {},
        }.get(event.stage, {})
        row = {
            "sequence": event.sequence,
            "timestamp": event.timestamp,
            "stage": event.stage,
            "transaction": min(1.0, float(prev["transaction"]) + float(bump.get("transaction", 0))),
            "device": min(1.0, float(prev["device"]) + float(bump.get("device", 0))),
            "graph": min(1.0, float(prev["graph"]) + float(bump.get("graph", 0))),
            "intent": min(1.0, float(prev["intent"]) + float(bump.get("intent", 0))),
            "anomaly": min(1.0, float(prev["anomaly"]) + float(bump.get("anomaly", 0))),
        }
        sig = event.risk_signals
        for key in ("transaction", "device", "graph", "intent", "anomaly"):
            if key in sig:
                row[key] = min(1.0, float(sig[key]))
        self.risk_series.append(row)

    def _build_plan(self) -> list[str]:
        return list(STAGES)

    def _run_stage(self, stage: str) -> list[SimEvent]:
        ent = self._entities()
        pay = self._payment()
        intent = dict(self.scenario.get("intent") or {})
        red = dict(self.scenario.get("red_team") or {})
        out: list[SimEvent] = []

        if stage == "reconnaissance":
            out.append(
                self.emit(
                    stage,
                    "profile_observed",
                    f"Synthetic customer {ent.get('customer_id')} observed. Device {ent.get('device_id')} is known.",
                    actor_type="customer",
                    actor_id=ent.get("customer_id") or "cust",
                    risk_signals={"transaction": 0.08, "device": 0.05},
                    provenance={"synthetic": True, "data_class": "public_demo"},
                    advance=0,
                )
            )
        elif stage == "social_engineering":
            out.append(
                self.emit(
                    stage,
                    "message_generated",
                    "Customer asks the shopping agent to buy a laptop under the ₹80,000 cap. No live message is sent.",
                    actor_type="customer",
                    actor_id=ent.get("customer_id") or "cust",
                    payload={"channel": "synthetic_chat", "live_message": False},
                    advance=8,
                )
            )
        elif stage == "identity_compromise":
            out.append(
                self.emit(
                    stage,
                    "login_attempt",
                    "Existing session reused. No new credentials. Identity is synthetic.",
                    actor_type="customer",
                    actor_id=ent.get("customer_id") or "cust",
                    payload={"new_credentials": False},
                    advance=6,
                )
            )
        elif stage == "agent_manipulation":
            if self.machine.state == "CREATED":
                self.machine.transition("INTENT_AUTHORIZED")
            if self.machine.state == "INTENT_AUTHORIZED":
                self.machine.transition("AGENT_EXECUTING")
            out.append(
                self.emit(
                    stage,
                    "intent_created",
                    f"Intent authorized: max ₹{intent.get('max_amount'):,.0f}, destination {ent.get('original_destination')}.",
                    actor_type="customer",
                    actor_id=ent.get("customer_id") or "cust",
                    provenance={"intent": intent},
                    advance=4,
                )
            )
            out.append(
                self.emit(
                    stage,
                    "tool_called",
                    "Agent calls merchant catalog tool.",
                    actor_type="agent",
                    actor_id=ent.get("agent_id") or "agent",
                    provenance={"tool": "merchant_catalog", "tool_trust": "UNTRUSTED"},
                    advance=4,
                )
            )
            out.append(
                self.emit(
                    stage,
                    "tool_output_received",
                    "Untrusted tool output received. Instructions are not executed on a live rail.",
                    actor_type="tool",
                    actor_id="merchant_catalog",
                    risk_signals={"intent": 0.28, "anomaly": 0.22},
                    provenance={
                        "tool": "merchant_catalog",
                        "tool_trust": "UNTRUSTED",
                        "agent_id": ent.get("agent_id"),
                    },
                    advance=6,
                )
            )
        elif stage == "payment_preparation":
            if self.machine.state == "AGENT_EXECUTING":
                self.machine.transition("PAYMENT_PREPARED")
            out.append(
                self.emit(
                    stage,
                    "payment_parameters_changed",
                    f"Destination changed {ent.get('original_destination')} → {ent.get('malicious_destination')}. Amount ₹{pay['amount']:,.0f} still under cap.",
                    actor_type="agent",
                    actor_id=ent.get("agent_id") or "agent",
                    risk_signals={"intent": 0.92, "graph": 0.55, "transaction": 0.22},
                    provenance={
                        "agent_id": ent.get("agent_id"),
                        "tool": "merchant_catalog",
                        "tool_trust": "UNTRUSTED",
                        "original_destination": ent.get("original_destination"),
                        "new_destination": ent.get("malicious_destination"),
                        "intent_scope_violation": True,
                    },
                    payload={"actions": red.get("actions")},
                    advance=6,
                )
            )
        elif stage == "payment_initiation":
            if self.machine.state == "PAYMENT_PREPARED":
                self.machine.transition("RISK_SCORING")
            out.append(
                self.emit(
                    stage,
                    "payment_requested",
                    f"Payment requested ₹{pay['amount']:,.0f} {pay['currency']} → {pay['destination']} on simulated {self.payment_rail}.",
                    actor_type="agent",
                    actor_id=ent.get("agent_id") or "agent",
                    provenance={"payment_rail": self.payment_rail, "live_execution": False},
                    advance=5,
                )
            )
        elif stage == "authorization":
            self._score()
            decision = (self.final_decision or {}).get("decision") or "REVIEW"
            ml = float((self.final_decision or {}).get("model_score") or 0)
            out.append(
                self.emit(
                    stage,
                    "risk_scored",
                    f"Detector score {ml:.2f}. Mode {self.mode}.",
                    actor_type="blue",
                    actor_id="detector",
                    risk_signals={
                        "transaction": ml,
                        "intent": float((self.intent_result or {}).get("score") or 0),
                        "anomaly": float((self.final_decision or {}).get("anomaly_score") or 0),
                        "graph": float((((self.detect_result or {}).get("layers") or {}).get("graph") or [0])[0] if isinstance((self.detect_result or {}).get("layers"), dict) else 0),
                    },
                    payload={"detect": _public_detect(self.detect_result), "mode": self.mode},
                    decision=decision,
                    advance=5,
                )
            )
            out.append(
                self.emit(
                    stage,
                    "policy_checked",
                    "Intent engine compared destination and amount to the signed cap.",
                    actor_type="blue",
                    actor_id="intent_policy",
                    provenance={"intent": intent, "payment": pay},
                    payload={"intent_result": self.intent_result},
                    decision=decision,
                    advance=1,
                )
            )
        elif stage == "intervention":
            decision = (self.final_decision or {}).get("decision") or "REVIEW"
            target = {"BLOCK": "BLOCKED", "APPROVE": "APPROVED", "REVIEW": "REVIEW", "STEP_UP": "STEP_UP"}[decision]
            if self.machine.state == "RISK_SCORING":
                self.machine.transition(target)
            etype = {
                "BLOCK": "payment_blocked",
                "APPROVE": "payment_approved",
                "REVIEW": "payment_reviewed",
                "STEP_UP": "payment_reviewed",
            }[decision]
            reasons = (self.final_decision or {}).get("reason_codes") or []
            out.append(
                self.emit(
                    stage,
                    etype,
                    f"Decision {decision}. " + (", ".join(reasons) if reasons else "No policy reasons."),
                    actor_type="blue",
                    actor_id="decision_engine",
                    decision=decision,
                    payload={"final": self.final_decision, "state": self.machine.state},
                    provenance={"policy_version": "intent-v1", "model_mode": self.mode},
                    advance=1,
                    status="final",
                )
            )
        elif stage == "settlement":
            decision = (self.final_decision or {}).get("decision")
            if decision == "APPROVE" and self.machine.state == "APPROVED":
                self.machine.transition("SETTLEMENT_SIMULATED")
                self.machine.transition("CASH_OUT_SIMULATED")
                out.append(
                    self.emit(
                        stage,
                        "settlement_simulated",
                        f"SIMULATED settlement to {pay['destination']}. No live funds moved.",
                        actor_type="rail",
                        actor_id="simulated_rail",
                        decision="APPROVE",
                        payload={"live_execution": False, "prevented": False},
                        advance=4,
                    )
                )
                out.append(
                    self.emit(
                        stage,
                        "cash_out_simulated",
                        "SIMULATED rapid cash-out on the mule beneficiary.",
                        actor_type="beneficiary",
                        actor_id=str(ent.get("beneficiary_id")),
                        payload={"live_execution": False},
                        advance=3,
                    )
                )
            else:
                out.append(
                    self.emit(
                        stage,
                        "settlement_simulated",
                        "SIMULATED: settlement prevented. Counterfactual cash-out did not run.",
                        actor_type="rail",
                        actor_id="simulated_rail",
                        decision="BLOCK",
                        payload={
                            "live_execution": False,
                            "prevented": True,
                            "potential_exposure": pay["amount"],
                            "counterfactual": [
                                "Payment approved",
                                f"Funds to {pay['destination']}",
                                "Rapid cash-out",
                                "Post-authorization alert",
                            ],
                        },
                        advance=3,
                    )
                )
        elif stage == "learning":
            self.learning = self._learn()
            if self.failure_artifact:
                out.append(
                    self.emit(
                        stage,
                        "hard_negative_created",
                        "Bypass stored as a validated hard negative. Not blindly retrained.",
                        actor_type="blue",
                        actor_id="closed_loop",
                        payload={"artifact": self.failure_artifact, "learning": self.learning},
                        advance=4,
                    )
                )
            else:
                out.append(
                    self.emit(
                        stage,
                        "model_retrained",
                        "Attack was caught. Registry notes a successful block on this scenario.",
                        actor_type="blue",
                        actor_id="closed_loop",
                        payload={"learning": self.learning},
                        advance=4,
                    )
                )
        return out

    def _score(self) -> None:
        pay = self._payment()
        intent = dict(self.scenario.get("intent") or {})
        self.intent_result = evaluate_intent(intent, pay)
        overlay = self._overlay_row()
        ml = 0.38
        anomaly = 0.12
        graph = 0.2
        detect: dict[str, Any] = {}
        if self.detect_fn is not None:
            try:
                detect = self.detect_fn(overlay) or {}
                ml = float((detect.get("fraud_probability") or [ml])[0])
                if detect.get("anomaly_score"):
                    anomaly = float(detect["anomaly_score"][0])
                layers = detect.get("layers") or {}
                if layers.get("graph"):
                    graph = float(layers["graph"][0])
            except Exception:  # noqa: BLE001
                detect = {"error": "detector_unavailable"}
        self.detect_result = detect
        self.final_decision = make_decision(
            model_score=ml,
            intent_result=self.intent_result,
            anomaly_score=anomaly,
            mode=self.mode,
        )
        self.final_decision["graph_score"] = graph
        self.final_decision["overlay"] = overlay
        self.final_decision["display_amount"] = pay["amount"]

    def _learn(self) -> dict[str, Any]:
        decision = (self.final_decision or {}).get("decision")
        ground = (self.scenario.get("red_team") or {}).get("ground_truth", "FRAUD")
        bypassed = decision == "APPROVE" and ground == "FRAUD"
        registry = load_registry()
        if bypassed:
            artifact = {
                "simulation_id": self.simulation_id,
                "scenario_id": self.scenario["scenario_id"],
                "transaction": self._payment(),
                "overlay": (self.final_decision or {}).get("overlay"),
                "model_version": "v1.4.2" if self.mode == "weak" else registry.get("current"),
                "detector_score": (self.final_decision or {}).get("model_score"),
                "decision": decision,
                "ground_truth": ground,
                "bypassed": True,
                "failure_reasons": [
                    "destination_deviation_not_used",
                    "beneficiary_novelty_underweighted",
                ],
                "recommended_features": [
                    "intent_scope_violation",
                    "beneficiary_graph_risk",
                ],
                "mode": self.mode,
            }
            self.failure_artifact = artifact
            if self.persist:
                append_failure(artifact)
                append_hard_negative(
                    {
                        "simulation_id": self.simulation_id,
                        "scenario_id": self.scenario["scenario_id"],
                        "validated": True,
                        "dedup_key": f"{self.scenario['scenario_id']}:destination_substitution",
                        "overlay": artifact.get("overlay"),
                        "ground_truth": 1,
                    }
                )
                register_version(
                    {
                        "version": "v1.4.3",
                        "label": "Intent + destination (full)",
                        "mode": "full",
                        "training_examples": 1,
                        "bypass_rate": 0.0,
                        "note": "Hard negative from amount-only miss. Evaluation is this scenario replay, not production.",
                        "evaluation": "SIMULATED EVALUATION",
                    }
                )
            return {
                "bypassed": True,
                "next_mode": "full",
                "new_version": "v1.4.3",
                "signal": "intent-to-destination mismatch",
            }
        return {
            "bypassed": False,
            "next_mode": self.mode,
            "new_version": registry.get("current"),
            "signal": "intent-to-destination mismatch" if decision == "BLOCK" else None,
        }

    def next_event(self) -> SimEvent | None:
        while self.cursor < len(self._plan):
            stage = self._plan[self.cursor]
            produced = self._run_stage(stage)
            self.cursor += 1
            if produced:
                return produced[-1] if len(produced) == 1 else produced[0]
        return None

    def step(self) -> dict[str, Any]:
        """Advance one lifecycle stage (may emit several events)."""
        if self.cursor >= len(self._plan):
            return self.get_state()
        stage = self._plan[self.cursor]
        self._run_stage(stage)
        self.cursor += 1
        return self.get_state()

    def run(self) -> dict[str, Any]:
        while self.cursor < len(self._plan):
            self.step()
        return self.get_state()

    def reset(self) -> dict[str, Any]:
        sid = self.simulation_id
        self.__init__(
            self.scenario["scenario_id"],
            seed=self.seed,
            mode=self.mode,
            detect_fn=self.detect_fn,
            persist=self.persist,
            payment_rail=self.payment_rail,
        )
        self.simulation_id = sid
        return self.get_state()

    def get_state(self) -> dict[str, Any]:
        pay = self._payment()
        ent = self._entities()
        done = self.cursor >= len(self._plan)
        stage = self._plan[min(self.cursor, len(self._plan) - 1)]
        decision = (self.final_decision or {}).get("decision")
        status = "complete" if done else ("awaiting_authorization" if self.cursor < 7 else "running")
        if self.machine.state == "RISK_SCORING":
            status = "awaiting_authorization_decision"
        if decision:
            status = f"decision_{decision.lower()}"
        return {
            "simulation_id": self.simulation_id,
            "scenario": {
                "scenario_id": self.scenario["scenario_id"],
                "name": self.scenario["name"],
                "severity": self.scenario.get("severity"),
                "attack_family": self.scenario.get("attack_family"),
                "description": self.scenario.get("description"),
                "expected_outcome": self.scenario.get("expected_outcome"),
            },
            "red_team": self.scenario.get("red_team"),
            "entities": ent,
            "intent": self.scenario.get("intent"),
            "payment": pay,
            "payment_rail": self.payment_rail,
            "mode": self.mode,
            "seed": self.seed,
            "status": status,
            "payment_state": self.machine.state,
            "state_history": list(self.machine.history),
            "progress": {"done": self.cursor, "total": len(self._plan), "stage": stage},
            "simulated_time_s": self.clock,
            "simulated_clock": clock_label(self.clock) if self.clock else "12:00:00",
            "events": [e.to_dict() for e in self.events],
            "risk_series": self.risk_series,
            "intent_result": self.intent_result,
            "final_decision": self.final_decision,
            "detect": _public_detect(self.detect_result),
            "failure_artifact": self.failure_artifact,
            "learning": self.learning,
            "safety": {
                "simulation_only": True,
                "synthetic_data": True,
                "live_payment_execution": False,
            },
        }


def _public_detect(detect: dict[str, Any] | None) -> dict[str, Any] | None:
    if not detect:
        return None
    layers = detect.get("layers") or {}
    return {
        "fraud_probability": (detect.get("fraud_probability") or [None])[0],
        "decision": (detect.get("decision") or [None])[0],
        "layers": {
            k: (layers.get(k) or [None])[0]
            for k in ("rules", "ml", "graph", "intent", "hybrid")
            if k in layers
        },
        "anomaly_score": (detect.get("anomaly_score") or [None])[0],
        "latency_ms": detect.get("inference_latency_ms") or detect.get("latency_ms"),
        "backend": detect.get("backend"),
        "explanations": (detect.get("explanations") or [[]])[0],
    }


def replay_before_after(
    scenario_id: str,
    detect_fn: DetectFn | None = None,
    persist: bool = True,
) -> dict[str, Any]:
    """Weak amount-only miss, then full intent replay of the same scenario."""
    weak = PaymentSimulation(scenario_id, mode="weak", detect_fn=detect_fn, persist=persist, seed=42)
    weak.run()
    full = PaymentSimulation(scenario_id, mode="full", detect_fn=detect_fn, persist=persist, seed=42)
    full.run()
    weak_dec = (weak.final_decision or {}).get("decision")
    full_dec = (full.final_decision or {}).get("decision")
    return {
        "scenario_id": scenario_id,
        "evaluation": "SIMULATED EVALUATION",
        "before": {
            "version": "v1.4.2",
            "mode": "weak",
            "decision": weak_dec,
            "detector_score": (weak.final_decision or {}).get("model_score"),
            "bypass_rate": 1.0 if weak_dec == "APPROVE" else 0.0,
            "destination_substitution": "MISSED" if weak_dec == "APPROVE" else "DETECTED",
            "simulation_id": weak.simulation_id,
            "state": weak.get_state(),
        },
        "after": {
            "version": "v1.4.3",
            "mode": "full",
            "decision": full_dec,
            "detector_score": (full.final_decision or {}).get("model_score"),
            "bypass_rate": 1.0 if full_dec == "APPROVE" else 0.0,
            "destination_substitution": "DETECTED" if full_dec == "BLOCK" else "MISSED",
            "simulation_id": full.simulation_id,
            "signal": (full.learning or {}).get("signal"),
            "state": full.get_state(),
        },
        "improvement": {
            "bypass_rate_before": 1.0 if weak_dec == "APPROVE" else 0.0,
            "bypass_rate_after": 1.0 if full_dec == "APPROVE" else 0.0,
            "new_signal": "intent-to-destination mismatch",
        },
    }


__all__ = ["PaymentSimulation", "list_scenarios", "load_scenario", "replay_before_after"]
