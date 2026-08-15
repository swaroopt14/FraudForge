"""Shared service layer used by FastAPI and Streamlit."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from agents.anomaly_detector import AnomalyDetector
from agents.attack_generator import AttackGenerator
from agents.hybrid_scorer import INTELLIGENCE_LAYERS, score_hybrid, score_intelligence_layer
from agents.feedback_agent import FeedbackAgent
from agents.fraud_detector import FraudDetector
from agents.fraud_research_agent import FraudResearchAgent
from agents.relational_scorer import RelationalScorer
from config import (
    ATTACK_FAMILIES,
    AUTOENCODER_PATH,
    CLOSED_LOOP_PATH,
    CREDITCARD_PATH,
    CTGAN_PATH,
    DETECTOR_PATH,
    FEATURE_COLUMNS,
    HOLDOUT_FAMILY,
    RANDOM_STATE,
    SCENARIOS_PATH,
)
from attack_catalog import (
    ATTACK_CATALOG,
    DIVERSITY_TARGET,
    FAMILY_LABELS,
    SIMULATABLE_FAMILIES,
    TAXONOMY,
    VECTOR_TO_FAMILY,
)
from agents.threat_intel import load_corpus
from data_loader import load_processed, load_raw
from db import init_db, save_attacks, save_evaluation, save_hypotheses
from features import (
    GENERATABLE_FAMILIES,
    TRAIN_FAMILY_WEIGHTS,
    ensure_narrative,
    feature_matrix,
    overlay_family,
)


class FraudForgeService:
    def __init__(self) -> None:
        self.detector: FraudDetector | None = None
        self.generator: AttackGenerator | None = None
        self.anomaly: AnomalyDetector | None = None
        self.research = FraudResearchAgent()
        self.feedback = FeedbackAgent(llm=self.research._llm)
        self.relational = RelationalScorer()
        self.processed: pd.DataFrame | None = None
        self._loaded = False
        self._novelty: dict[str, Any] | None = None
        self._sims: dict[str, Any] = {}

    def load(self, require_models: bool = False) -> dict[str, bool]:
        init_db()
        status = {
            "detector": DETECTOR_PATH.exists(),
            "ctgan": CTGAN_PATH.exists() and CTGAN_PATH.stat().st_size > 20,
            "autoencoder": AUTOENCODER_PATH.exists(),
            "data": CREDITCARD_PATH.exists(),
        }
        if status["detector"]:
            self.detector = FraudDetector.load()
        elif require_models:
            raise FileNotFoundError("detector.pkl missing — run python scripts/train_all.py")

        fraud_df = None
        if status["data"]:
            raw = load_raw()
            fraud_df = raw.loc[raw["Class"] == 1].copy()

        if status["ctgan"] or fraud_df is not None:
            self.generator = AttackGenerator.load(fraud_samples=fraud_df)
            if fraud_df is not None:
                self.generator.fraud_samples = fraud_df

        if status["autoencoder"]:
            try:
                self.anomaly = AnomalyDetector.load()
            except Exception:  # noqa: BLE001
                self.anomaly = None

        try:
            if status["data"]:
                raw = load_raw() if fraud_df is None else None
                table = load_raw() if raw is None else raw
                fraud_s = table.loc[table["Class"] == 1]
                legit_s = table.loc[table["Class"] == 0]
                sample = pd.concat(
                    [
                        fraud_s.sample(min(200, len(fraud_s)), random_state=RANDOM_STATE),
                        legit_s.sample(min(2300, len(legit_s)), random_state=RANDOM_STATE),
                    ],
                    ignore_index=True,
                )
                from features import overlay_real_dataset

                self.relational.fit_context(overlay_real_dataset(sample), n=2500)
        except Exception:  # noqa: BLE001
            pass

        self._loaded = True
        return status

    def ensure_processed(self) -> pd.DataFrame:
        if self.processed is None:
            self.processed = load_processed()
        return self.processed

    def hypotheses(self, threat_intel: str) -> list[dict[str, Any]]:
        return self.discover(threat_intel)["hypotheses"]

    def discover(self, threat_intel: str = "", fetch_live: bool = False) -> dict[str, Any]:
        result = self.research.discover(threat_intel, fetch_live=fetch_live)
        save_hypotheses(result.get("hypotheses") or [])
        return result

    def intel_sources(self) -> list[dict[str, Any]]:
        return load_corpus()

    def generate_attacks(
        self,
        n_samples: int = 500,
        family: str | None = None,
        intensity: str = "medium",
        from_legitimate: bool = False,
    ) -> dict[str, Any]:
        if self.generator is None:
            self.load()
        if self.generator is None:
            raise RuntimeError("Attack generator is not available")
        family = None if family in {None, "", "mixed"} else family
        if family in VECTOR_TO_FAMILY:
            family = VECTOR_TO_FAMILY[family]
        if family and family not in GENERATABLE_FAMILIES:
            raise ValueError(f"Family {family} is not generatable")
        if family:
            processed = self.ensure_processed()
            legit = processed.loc[processed["Class"] == 0]
            packed = self.generator.generate_from_legitimate(
                legit,
                n_samples=n_samples,
                family=family,
                intensity="medium" if intensity == "adaptive" else intensity,
            )
            synth = pd.DataFrame(packed["transactions"])
            if intensity == "adaptive" and self.detector is not None:
                from agents.adversarial_optimizer import AdversarialOptimizer

                synth = AdversarialOptimizer(self.detector).generate_adversarial_attacks(synth)
                packed["generation_method"] = "rules+adaptive"
                packed["mutation_contract"] = packed.get("mutation_contract") or {}
            mutation = packed
            _ = from_legitimate
        else:
            synth = self.generator.generate_mixed_families(n_samples, GENERATABLE_FAMILIES)
            mutation = None
        real = self.generator.fraud_samples if self.generator.fraud_samples is not None else synth
        fidelity = self.generator.evaluate_fidelity(synth, real)
        method = (mutation or {}).get("generation_method") or self.generator.method
        success = None
        if self.detector is None:
            self.load()
        if self.detector is not None:
            scored = ensure_narrative(synth)
            proba = self.detector.predict(scored)
            thr = float(self.detector.threshold)
            bypassed = proba < thr
            success = {
                "threshold": thr,
                "mean_fraud_probability": float(np.mean(proba)),
                "attack_success_rate": float(np.mean(bypassed)),
                "detected_rate": float(np.mean(~bypassed)),
                "bypassed": int(bypassed.sum()),
                "detected": int((~bypassed).sum()),
                "n": int(len(proba)),
            }
        preview_cols = [
            c
            for c in [
                "Amount",
                "attack_family",
                "device_new",
                "velocity_1h",
                "location_mismatch",
                "beneficiary_name_match",
                "mule_account_risk",
                "constraint_violation",
                "generation_method",
            ]
            if c in synth.columns
        ]
        counts = {}
        if "attack_family" in synth.columns:
            counts = {str(k): int(v) for k, v in synth["attack_family"].value_counts().items()}
        save_attacks(method, family, synth.head(20).to_dict(orient="records"))
        card = self.research.scenario_card(family or "mixed", int(len(synth)), method)
        return {
            "n": int(len(synth)),
            "family": family or "mixed",
            "method": method,
            "scenario_card": card,
            "family_counts": counts,
            "preview": json.loads(synth[preview_cols].head(15).to_json(orient="records")),
            "amount_real": real["Amount"].astype(float).tolist()[:4000] if "Amount" in real.columns else [],
            "amount_synthetic": synth["Amount"].astype(float).tolist(),
            "mule_synthetic": synth["mule_account_risk"].astype(float).tolist()
            if "mule_account_risk" in synth.columns
            else [],
            "velocity_synthetic": synth["velocity_1h"].astype(float).tolist()
            if "velocity_1h" in synth.columns
            else [],
            "fidelity": fidelity,
            "attack_success": success,
            "intensity": intensity,
            "mutation": mutation,
        }

    def detect_rows(
        self,
        rows: list[dict[str, Any]] | pd.DataFrame,
        explain: bool = True,
    ) -> dict[str, Any]:
        if self.detector is None:
            self.load()
        if self.detector is None:
            raise RuntimeError("Detector is not trained")
        started = time.perf_counter()
        df = pd.DataFrame(rows) if not isinstance(rows, pd.DataFrame) else rows
        df = ensure_narrative(df)
        infer_started = time.perf_counter()
        proba = self.detector.predict(df)
        inference_latency_ms = (time.perf_counter() - infer_started) * 1000.0
        anomaly_scores = None
        anomaly_flags = None
        if self.anomaly is not None:
            X = feature_matrix(df).to_numpy(dtype=np.float32)
            anomaly_scores = self.anomaly.predict(X)
            anomaly_flags = self.anomaly.is_anomaly(X)
        explanations = []
        if explain:
            for i in range(min(len(df), 8)):
                explanations.append(self.detector.explain_row(df.iloc[[i]], top_k=5).to_dict(orient="records"))
        relational = self.relational.score(df)
        rel_scores = np.asarray(relational.get("scores") or [0.0] * len(df), dtype=float)
        layers = score_hybrid(df, proba, rel_scores, float(self.detector.threshold))
        ensemble = np.asarray(layers["hybrid"], dtype=float)
        out = {
            "threshold": self.detector.threshold,
            "metrics": self.detector.metrics,
            "backend": self.detector.backend,
            "fraud_probability": proba.tolist(),
            "risk_score": (proba * 100).tolist(),
            "label": layers["block"],
            "decision": layers["decision"],
            "explanations": explanations,
            "relational": relational,
            "ensemble_probability": ensemble.tolist(),
            "ensemble_risk_score": (ensemble * 100).tolist(),
            "layers": layers,
            "intelligence": {
                key: [score_intelligence_layer(layers, key, i) for i in range(len(df))]
                for key in INTELLIGENCE_LAYERS
            },
            "inference_latency_ms": round(inference_latency_ms, 3),
            "latency_ms": round((time.perf_counter() - started) * 1000.0, 3),
            "n": int(len(df)),
        }
        if anomaly_scores is not None:
            out["anomaly_score"] = anomaly_scores.tolist()
            out["is_anomaly"] = anomaly_flags.tolist()
            out["anomaly_threshold"] = self.anomaly.threshold
        return out

    def run_red_demo(
        self,
        family: str = "prompt_injection_pay",
        intensity: str = "medium",
    ) -> dict[str, Any]:
        """Backend-backed red-team play: mutate one legit row for the demo pages."""
        if family not in GENERATABLE_FAMILIES:
            family = "prompt_injection_pay"
        if self.generator is None:
            self.load()
        processed = self.ensure_processed()
        legit = processed.loc[processed["Class"] == 0]
        packed = self.generator.generate_from_legitimate(
            legit, n_samples=1, family=family, intensity=intensity
        )
        txn = packed["transactions"][0]
        safe_txn = {k: _json_safe(v) for k, v in txn.items() if k in FEATURE_COLUMNS or k in {"attack_family", "Class", "generation_method", "mutation_intensity"}}
        meta = ATTACK_CATALOG.get(family) or {}
        return {
            "family": family,
            "label": meta.get("name") or family,
            "intensity": intensity,
            "generation_method": packed["generation_method"],
            "before": packed["before"],
            "after": packed["after"],
            "changed_columns": packed["changed_columns"],
            "unchanged_columns": packed["unchanged_columns"],
            "transaction": safe_txn,
            "surface": meta.get("attack_surface"),
            "ai_component": meta.get("ai_component"),
            "signal_layers": meta.get("signal_layers") or {},
            "safety": [
                "No live payment networks, UPI, card, or wallet calls",
                "No real phishing email or SMS",
                "No contact with victims",
                "No stolen credentials or real account takeover",
                "No unauthorized tests against third-party systems",
            ],
        }

    def run_blue_demo(self, transaction: dict[str, Any] | None = None) -> dict[str, Any]:
        """Score a red-team row with hybrid layers for the blue-team page."""
        if not transaction:
            red = self.run_red_demo()
            transaction = red["transaction"]
            family = red["family"]
        else:
            family = str(transaction.get("attack_family") or "prompt_injection_pay")
        scored = self.detect_rows([transaction], explain=True)
        layers = scored.get("layers") or {}
        row = transaction
        checks = [
            {
                "id": "destination",
                "label": "Destination differs from original intent",
                "hit": float(row.get("beneficiary_name_match", 1) or 0) < 0.5,
                "layer": "rules",
            },
            {
                "id": "merchant",
                "label": "Merchant is not in the approved set",
                "hit": float(row.get("constraint_violation", 0) or 0) >= 1,
                "layer": "intent",
            },
            {
                "id": "tool",
                "label": "Tool output changed a payment parameter",
                "hit": float(row.get("constraint_violation", 0) or 0) >= 1
                or float(row.get("beneficiary_name_match", 1) or 0) < 0.5,
                "layer": "intent",
            },
            {
                "id": "scope",
                "label": "Agent authorization scope was exceeded",
                "hit": float(row.get("amount_vs_limit_ratio", 0) or 0) > 1
                or float(row.get("constraint_violation", 0) or 0) >= 1,
                "layer": "intent",
            },
            {
                "id": "mule",
                "label": "New beneficiary has high network risk",
                "hit": float(row.get("mule_account_risk", 0) or 0) >= 0.4,
                "layer": "graph",
            },
            {
                "id": "provenance",
                "label": "Provenance chain is incomplete",
                "hit": float(row.get("constraint_violation", 0) or 0) >= 1,
                "layer": "intent",
            },
            {
                "id": "history",
                "label": "Inconsistent with the user's historical behavior",
                "hit": float((scored.get("fraud_probability") or [0])[0]) >= float(scored.get("threshold") or 0),
                "layer": "ml",
            },
        ]
        return {
            "family": family,
            "transaction": {k: _json_safe(v) for k, v in row.items()},
            "decision": (scored.get("decision") or ["APPROVE"])[0],
            "layers": {
                key: (layers.get(key) or [0])[0]
                for key in ["rules", "ml", "graph", "intent", "hybrid"]
            },
            "latency_ms": scored.get("latency_ms"),
            "inference_latency_ms": scored.get("inference_latency_ms"),
            "checks": checks,
            "explanations": (scored.get("explanations") or [[]])[0],
            "threshold": scored.get("threshold"),
            "backend": scored.get("backend"),
        }

    def novelty_coverage(self, n_per_family: int = 16) -> dict[str, Any]:
        """Coverage of catalog families that were never used as overlay on the train set."""
        if self._novelty is not None:
            return self._novelty
        if self.detector is None:
            self.load()
        if self.detector is None:
            raise RuntimeError("Detector is not trained")

        from agents.evaluation_agent import EvaluationAgent

        trained = set(TRAIN_FAMILY_WEIGHTS)
        catalog = set(ATTACK_CATALOG)
        novel_families = sorted(catalog - trained)
        processed = self.ensure_processed()
        legit = processed.loc[processed["Class"] == 0]
        rng = np.random.default_rng(RANDOM_STATE + 7)
        evaluator = EvaluationAgent(self.detector)
        per_family: dict[str, Any] = {}
        for family in novel_families:
            if family not in GENERATABLE_FAMILIES:
                continue
            idx = rng.choice(len(legit), size=min(n_per_family, len(legit)), replace=False)
            seed = legit.iloc[idx].copy().reset_index(drop=True)
            attacks = overlay_family(seed, family, rng, set_amount=True)
            attacks["Class"] = 1
            attacks["attack_family"] = family
            stats = evaluator.evaluate_attack_success(attacks)
            per_family[family] = {
                "label": FAMILY_LABELS.get(family, family),
                "in_training": False,
                **stats,
            }

        rates = [float(v["attack_success_rate"]) for v in per_family.values()]
        loop: dict[str, Any] = {}
        if CLOSED_LOOP_PATH.exists():
            loop_data = json.loads(CLOSED_LOOP_PATH.read_text())
            before = loop_data.get("attack_success_before") or {}
            after = loop_data.get("attack_success_after") or {}
            loop = {
                "holdout_family": loop_data.get("holdout_family"),
                "n_holdout_attacks": loop_data.get("n_holdout_attacks"),
                "attack_success_before": before.get("attack_success_rate"),
                "attack_success_after": after.get("attack_success_rate"),
                "source": "washed_legit_pca + adversarial (not ULB labeled fraud)",
                "holdout_family_in_training_weights": HOLDOUT_FAMILY in trained,
                "optimizer": "evolutionary_perturbation",
            }

        n_catalog = len(catalog)
        n_novel = len(novel_families)
        self._novelty = {
            "trained_families": sorted(trained),
            "novel_families": novel_families,
            "n_catalog_families": n_catalog,
            "n_novel_families": n_novel,
            "novel_family_coverage": (n_novel / n_catalog) if n_catalog else 0.0,
            "mean_novel_attack_success": float(np.mean(rates)) if rates else 0.0,
            "novel_detection_rate": float(1.0 - np.mean(rates)) if rates else 0.0,
            "per_family": per_family,
            "closed_loop": loop,
            "note": (
                "Judge families stay in TRAIN_FAMILY_WEIGHTS so scenarios 1–3 BLOCK. "
                "Novelty is catalog families never overlaid on the original train set, "
                "plus closed-loop washed holdout rows that were not ULB-labeled fraud."
            ),
        }
        return self._novelty

    def scenario_transaction(self, scenario_id: str) -> dict[str, Any]:
        scenarios = load_scenarios()
        for item in scenarios:
            if item["id"] == scenario_id:
                return item
        raise KeyError(scenario_id)

    def closed_loop(self, live: bool = False) -> dict[str, Any]:
        if CLOSED_LOOP_PATH.exists() and not live:
            data = json.loads(CLOSED_LOOP_PATH.read_text())
            save_evaluation(data)
            return data
        if live:
            from closed_loop import run_closed_loop

            data = run_closed_loop(persist=True)
            save_evaluation(data)
            return data
        raise FileNotFoundError("closed_loop.json missing — run python scripts/train_all.py")

    def metrics(self) -> dict[str, Any]:
        if self.detector is None:
            self.load()
        payload: dict[str, Any] = {
            "detector": self.detector.metrics if self.detector else {},
            "threshold": self.detector.threshold if self.detector else None,
            "families": ATTACK_FAMILIES,
            "discovery_families": list(ATTACK_CATALOG.keys()),
            "simulatable_families": SIMULATABLE_FAMILIES,
            "family_labels": FAMILY_LABELS,
            "intel_sources": len(load_corpus()),
            "identify": {
                "catalog_size": len(ATTACK_CATALOG),
                "taxonomy": TAXONOMY,
                "n_taxonomy": len(TAXONOMY),
                "simulatable": len(SIMULATABLE_FAMILIES),
                "identified_only": len(ATTACK_CATALOG) - len(SIMULATABLE_FAMILIES),
                "diversity_target": DIVERSITY_TARGET,
                "provider": getattr(self.research, "provider", None),
                "graph_runtime": getattr(self.research, "graph_runtime", None),
            },
            "holdout_family": HOLDOUT_FAMILY,
            "llm_fallback": self.research.using_fallback,
            "tree_backend": self.detector.backend if self.detector else None,
            "relational_backend": self.relational.backend,
            "relational": self.relational.metrics,
            "models": {
                "detector": DETECTOR_PATH.exists(),
                "ctgan": CTGAN_PATH.exists() and CTGAN_PATH.stat().st_size > 20,
                "autoencoder": AUTOENCODER_PATH.exists(),
                "closed_loop": CLOSED_LOOP_PATH.exists(),
            },
        }
        if CLOSED_LOOP_PATH.exists():
            payload["closed_loop"] = json.loads(CLOSED_LOOP_PATH.read_text())
            payload["closed_loop"]["optimizer"] = "evolutionary_perturbation"
        try:
            payload["novelty"] = self.novelty_coverage()
        except Exception:  # noqa: BLE001
            payload["novelty"] = None
        return payload

    def _detect_overlay(self, row: dict[str, Any]) -> dict[str, Any]:
        return self.detect_rows([row], explain=True)

    def list_sim_scenarios(self) -> list[dict[str, Any]]:
        from simulation.scenarios import list_scenarios

        return list_scenarios()

    def start_simulation(
        self,
        scenario_id: str = "agent_destination_substitution",
        *,
        mode: str = "full",
        payment_rail: str | None = None,
        seed: int = 42,
    ) -> dict[str, Any]:
        from simulation.engine import PaymentSimulation

        if self.detector is None:
            self.load()
        sim = PaymentSimulation(
            scenario_id,
            seed=seed,
            mode=mode,
            detect_fn=self._detect_overlay if self.detector is not None else None,
            persist=True,
            payment_rail=payment_rail,
        )
        self._sims[sim.simulation_id] = sim
        return sim.get_state()

    def get_simulation(self, simulation_id: str) -> dict[str, Any]:
        sim = self._sims.get(simulation_id)
        if sim is None:
            raise KeyError(simulation_id)
        return sim.get_state()

    def step_simulation(self, simulation_id: str) -> dict[str, Any]:
        sim = self._sims.get(simulation_id)
        if sim is None:
            raise KeyError(simulation_id)
        return sim.step()

    def run_simulation(self, simulation_id: str) -> dict[str, Any]:
        sim = self._sims.get(simulation_id)
        if sim is None:
            raise KeyError(simulation_id)
        return sim.run()

    def reset_simulation(self, simulation_id: str) -> dict[str, Any]:
        sim = self._sims.get(simulation_id)
        if sim is None:
            raise KeyError(simulation_id)
        return sim.reset()

    def replay_simulation(self, scenario_id: str = "agent_destination_substitution") -> dict[str, Any]:
        from simulation.engine import replay_before_after

        if self.detector is None:
            self.load()
        return replay_before_after(
            scenario_id,
            detect_fn=self._detect_overlay if self.detector is not None else None,
            persist=True,
        )

    def flagship_demo(self) -> dict[str, Any]:
        """One-click: weak miss → hard negative → full BLOCK on the same attack."""
        return self.replay_simulation("agent_destination_substitution")


_SERVICE: FraudForgeService | None = None


def get_service() -> FraudForgeService:
    global _SERVICE
    if _SERVICE is None:
        _SERVICE = FraudForgeService()
        _SERVICE.load()
    return _SERVICE


def build_scenario_fixtures(processed: pd.DataFrame | None = None) -> list[dict[str, Any]]:
    """Build the four judge-facing scenario payloads."""
    rng = np.random.default_rng(RANDOM_STATE)
    if processed is None and CREDITCARD_PATH.exists():
        processed = load_processed()
    base = None
    if processed is not None:
        fraud = processed.loc[processed["Class"] == 1]
        if len(fraud):
            base = fraud.sample(3, random_state=RANDOM_STATE).reset_index(drop=True)

    def row_from_family(family: str, fallback_amount: float) -> dict[str, Any]:
        if base is not None:
            seed = base.iloc[[0]].copy()
        else:
            seed = pd.DataFrame([{c: 0.0 for c in FEATURE_COLUMNS}])
            seed["Time"] = 50000.0
            seed["Amount"] = fallback_amount
        seeded = overlay_family(seed, family, rng, set_amount=True)
        rec = {c: _json_safe(seeded.iloc[0][c]) for c in FEATURE_COLUMNS if c in seeded.columns}
        rec["Class"] = 1
        rec["attack_family"] = family
        return rec

    return [
        {
            "id": "phishing_ato",
            "title": "AI Phishing → Account Takeover",
            "threat_intel": "AI phishing scams targeting bank customers (Feb 2026).",
            "expected_decision": "BLOCK",
            "narrative": "New device, velocity spike, cross-border session, high-value CNP purchase.",
            "transaction": row_from_family("phishing_ato", 2100.0),
        },
        {
            "id": "deepfake_upi",
            "title": "Deepfake Voice → UPI Collect Request",
            "threat_intel": "Deepfake voice scams impersonating family members (Jan 2026).",
            "expected_decision": "BLOCK",
            "narrative": "Collect-style debit to a mule beneficiary after a voice clone call.",
            "transaction": row_from_family("deepfake_upi", 640.0),
        },
        {
            "id": "malicious_agent",
            "title": "Malicious AI Agent → Constraint Violation",
            "threat_intel": "Compromised AI agents making unauthorized payments.",
            "expected_decision": "BLOCK",
            "narrative": "Delegated agent exceeds the $1,500 spend constraint.",
            "transaction": row_from_family("malicious_agent", 2000.0),
        },
        {
            "id": "closed_loop",
            "title": "Closed-Loop Improvement",
            "threat_intel": "Retrain the detector on novel and adversarial attacks.",
            "expected_decision": None,
            "narrative": "Attack success should drop after the detector sees the hold-out family.",
            "transaction": None,
        },
    ]


def load_scenarios() -> list[dict[str, Any]]:
    if SCENARIOS_PATH.exists():
        return json.loads(SCENARIOS_PATH.read_text())
    return build_scenario_fixtures()


def _json_safe(value: Any) -> Any:
    if isinstance(value, (np.floating, float)):
        return float(value)
    if isinstance(value, (np.integer, int)):
        return int(value)
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    return value


__all__ = ["FraudForgeService", "build_scenario_fixtures", "get_service", "load_scenarios"]
