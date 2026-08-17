"""Deterministic Red Team controller: select → configure → simulate → score → report."""

from __future__ import annotations

import json
import uuid
from typing import Any

import numpy as np
import pandas as pd

from app.blue_team.context import P2_COLUMNS
from app.core.config import FEATURE_COLUMNS, RANDOM_STATE, SIM_DIR, ensure_dirs
from app.core.db import session
from app.data.schema import AgentEvent, GraphEdge, PaymentRow, RedTeamRun
from app.evaluation.fidelity import fidelity_report
from app.fraud.pipeline import compute_metrics
from app.redteam.agents import agent_events_from_frame, attach_agent_intent
from app.redteam.contract import AttackContract
from app.redteam.difficulty import adaptive_mutation, resolve_mutation
from app.redteam.graph import build_edge_table, edge_fingerprint, graph_payload, network_fidelity
from app.redteam.mutations import apply_mutation, entity_stats
from app.redteam.report import render_red_team_report
from app.risk.explain import explain_row
from app.risk.policy import decide
from app.simulation.legit import fit_profiles, generate_legitimate
from app.threats.registry import ThreatRegistry, get_registry
from app.threats.schema import MutationParams


class RedTeamController:
    def __init__(self, payments: pd.DataFrame, team: Any, registry: ThreatRegistry | None = None) -> None:
        self.payments = payments
        self.team = team
        self.registry = registry or get_registry()
        self._profiles = None
        self._corpus = None

    def profiles(self):
        if self._profiles is None:
            self._profiles = fit_profiles(self.payments)
        return self._profiles

    def corpus(self):
        if self._corpus is None:
            from app.data.history import CorpusHistory

            self._corpus = CorpusHistory.from_payments(self.payments)
        return self._corpus

    def build_contract(
        self,
        attack_id: str,
        *,
        variant_id: str | None = None,
        difficulty: str = "MEDIUM",
        transaction_count: int = 1000,
        seed: int = RANDOM_STATE,
        target_population: str = "normal_customers",
    ) -> AttackContract:
        threat = self.registry.get(attack_id)
        variant = self.registry.resolve_variant(attack_id, variant_id)
        mutation = resolve_mutation(self.registry, threat.attack_id, difficulty, variant.id)
        if difficulty.upper() == "ADAPTIVE":
            mutation = adaptive_mutation(self.registry, threat.attack_id, variant.id, 0.5)
        return AttackContract(
            attack_id=threat.attack_id,
            variant_id=variant.id,
            family=threat.family,
            difficulty=difficulty.upper(),
            seed=int(seed),
            transaction_count=int(transaction_count),
            target_population=target_population,
            mutation=mutation,
            detection_signals=list(threat.detection_signals),
        )

    def generate(self, contract: AttackContract) -> pd.DataFrame:
        base = generate_legitimate(
            self.profiles(),
            contract.transaction_count,
            seed=contract.seed,
            history=self.corpus(),
            source=self.payments,
        )
        rng = np.random.default_rng(contract.seed)
        rows = apply_mutation(base, contract.mutation, rng, contract.family)
        rows = self.corpus().attach(rows, refresh_concentration=False)
        from app.blue_team.context import attach_p2_features

        rows = attach_p2_features(rows)
        rows["transaction_id"] = [
            f"{contract.attack_id}-{contract.variant_id}-{contract.seed}-{i}" for i in range(len(rows))
        ]
        rows["attack_id"] = contract.attack_id
        rows["variant_id"] = contract.variant_id
        rows["seed"] = contract.seed
        rows["ground_truth"] = rows["fraud_label"]
        rows, events = attach_agent_intent(rows, contract.family, np.random.default_rng(contract.seed + 17))
        rows.attrs["agent_events"] = events
        return rows

    def run(
        self,
        attack_id: str,
        *,
        variant_id: str | None = None,
        difficulty: str = "MEDIUM",
        transaction_count: int = 1000,
        seed: int = RANDOM_STATE,
        target_population: str = "normal_customers",
        persist: bool = True,
        explain: bool = True,
    ) -> dict[str, Any]:
        level = (difficulty or "MEDIUM").upper()
        if level == "ADAPTIVE":
            contract = self._adaptive_contract(
                attack_id,
                variant_id=variant_id,
                transaction_count=transaction_count,
                seed=seed,
                target_population=target_population,
            )
        else:
            contract = self.build_contract(
                attack_id,
                variant_id=variant_id,
                difficulty=difficulty,
                transaction_count=transaction_count,
                seed=seed,
                target_population=target_population,
            )
        return self.execute(contract, persist=persist, explain=explain)

    def _adaptive_contract(
        self,
        attack_id: str,
        *,
        variant_id: str | None,
        transaction_count: int,
        seed: int,
        target_population: str,
    ) -> AttackContract:
        probe_n = min(80, max(20, int(transaction_count // 10) or 20))
        probe = self.build_contract(
            attack_id,
            variant_id=variant_id,
            difficulty="MEDIUM",
            transaction_count=probe_n,
            seed=seed,
            target_population=target_population,
        )
        det = float((self.team.score(self.generate(probe)) >= 0.5).mean())
        threat = self.registry.get(attack_id)
        variant = self.registry.resolve_variant(attack_id, variant_id)
        mutation = adaptive_mutation(self.registry, threat.attack_id, variant.id, det)
        return AttackContract(
            attack_id=threat.attack_id,
            variant_id=variant.id,
            family=threat.family,
            difficulty="ADAPTIVE",
            seed=int(seed),
            transaction_count=int(transaction_count),
            target_population=target_population,
            mutation=mutation,
            detection_signals=list(threat.detection_signals),
        )

    def execute(self, contract: AttackContract, persist: bool = True, explain: bool = True) -> dict[str, Any]:
        ensure_dirs()
        import time

        t0 = time.perf_counter()
        rows = self.generate(contract)
        t_gen = time.perf_counter()
        threat = self.registry.get(contract.attack_id)
        proba = self.team.score(rows)
        t_score = time.perf_counter()
        mid = str(getattr(self.team, "model_id", "BLUE-0.1.0"))
        if (mid.startswith("BLUE-0.1.") and not mid.startswith("BLUE-0.1.0")) or mid.startswith("BLUE-0.2"):
            from app.blue_team.risk import decide_v011

            decisions = [decide_v011(int(round(min(1.0, max(0.0, float(p))) * 100))) for p in proba]
        else:
            decisions = [decide(float(p)) for p in proba]
        y = rows["fraud_label"].to_numpy()
        attack_metrics = compute_metrics(y, proba)
        extra_cols = [
            "attack_id",
            "variant_id",
            "agent_id",
            "intent_id",
            "agent_in_scope",
            "intent_match",
            "seed",
            "ground_truth",
            "simulation_id",
        ]
        legit = self.payments.loc[self.payments["fraud_label"] == 0]
        if len(legit):
            hold_n = min(len(legit), max(200, contract.transaction_count // 5))
            hold = legit.sample(hold_n, random_state=contract.seed)
            mix = pd.concat([rows.drop(columns=extra_cols, errors="ignore"), hold], ignore_index=True)
            metrics = compute_metrics(mix["fraud_label"].to_numpy(), self.team.score(mix))
            fid_src = hold
        else:
            metrics = dict(attack_metrics)
            fid_src = rows
        metrics["detection_rate"] = attack_metrics["recall"]
        metrics["attack_success_rate"] = 1.0 - attack_metrics["recall"]
        missed_idx = [i for i, p in enumerate(proba) if float(p) < 0.5]
        try:
            fidelity = fidelity_report(fid_src.head(min(len(fid_src), 4000)), rows.head(min(len(rows), 4000)))
        except Exception:
            fidelity = {"overall_fidelity": 0.0, "merchant_distribution": 0.0}
        graph = graph_payload(
            rows,
            family=contract.family,
            attack_id=contract.attack_id,
            variant_id=contract.variant_id,
            scores=proba,
        )
        agent_events = agent_events_from_frame(rows)
        legit_edges = build_edge_table(fid_src.head(min(len(fid_src), 2000))) if len(fid_src) else []
        fidelity["network_fidelity"] = network_fidelity(graph["edge_table"], legit_edges)
        entities = entity_stats(rows)
        entities["attack_networks"] = graph["attack_networks"]
        from app.blue_team.context import network_summary

        context_view = network_summary(rows)
        if mid.startswith("BLUE-0.2"):
            from app.blue_team.risk import combine_p2

            net_mean = float(pd.to_numeric(rows.get("network_risk"), errors="coerce").fillna(0.0).mean()) if "network_risk" in rows.columns else 0.0
            geo_mean = float(pd.to_numeric(rows.get("geo_risk"), errors="coerce").fillna(0.0).mean()) if "geo_risk" in rows.columns else 0.0
            risk_lanes = combine_p2(float(np.mean(proba)), network_risk=net_mean, geo_risk=geo_mean)
        else:
            risk_lanes = None
        run_id = uuid.uuid4().hex[:8]
        finding = (
            f"{threat.name} at {contract.difficulty} evades {metrics['attack_success_rate']:.1%} of scored attacks."
            if metrics["attack_success_rate"] > 0.15
            else f"{threat.name} at {contract.difficulty} is largely visible to the current detector."
        )
        payload_rows = []
        for i, row in rows.reset_index(drop=True).iterrows():
            rec = {k: row[k] for k in row.index if k in FEATURE_COLUMNS or k in P2_COLUMNS or k in (
                "transaction_id", "amount", "attack_family", "fraud_label", "customer_id", "merchant_id",
                "device_id", "beneficiary_id", "ip_id", "attack_id", "variant_id", "seed", "ground_truth",
            )}
            rec["simulation_id"] = run_id
            rec["fraud_probability"] = float(proba[i])
            rec["decision"] = decisions[i]
            rec["missed"] = i in missed_idx
            if explain and (i < 40 or i in missed_idx[:20]):
                rec["explanation"] = explain_row(
                    self.team.lgbm, pd.DataFrame([row]), columns=list(getattr(self.team, "feature_names", FEATURE_COLUMNS))
                )
            payload_rows.append(rec)
        result = {
            "simulation_id": run_id,
            "attack_id": contract.attack_id,
            "attack_name": threat.name,
            "attack_family": contract.family,
            "variant_id": contract.variant_id,
            "difficulty": contract.difficulty,
            "seed": contract.seed,
            "target_population": contract.target_population,
            "generated": int(contract.transaction_count),
            "detected": int(contract.transaction_count - len(missed_idx)),
            "missed": int(len(missed_idx)),
            "detection_rate": float(metrics["detection_rate"]),
            "metrics": metrics,
            "fidelity": fidelity,
            "entities": entities,
            "context": context_view,
            "risk_lanes": risk_lanes,
            "detection_signals": threat.detection_signals,
            "bypass_signals": threat.detection_signals,
            "finding": finding,
            "contract": contract.fingerprint(),
            "model_version": self.team.version() if hasattr(self.team, "version") else "BLUE-0.1.0",
            "missed_transactions": [payload_rows[i] for i in missed_idx[:50]],
            "preview": payload_rows[:12],
            "graph": {
                "nodes": graph["nodes"],
                "edges": graph["edges"],
                "n_edges": graph["n_edges"],
                "n_nodes": graph["n_nodes"],
                "shared_hubs": graph["shared_hubs"],
                "attack_networks": graph["attack_networks"],
                "edge_fingerprint": edge_fingerprint(graph["edge_table"]),
                "family": graph.get("family"),
                "attack_id": graph.get("attack_id"),
                "variant_id": graph.get("variant_id"),
                "stats": graph.get("stats") or {},
                "focus": graph.get("focus") or {"nodes": [], "edges": []},
                "path": graph.get("path") or [],
                "blue": graph.get("blue") or [],
                "motif": graph.get("motif") or [],
            },
            "agent_events": agent_events[:200],
            "agent_event_count": len(agent_events),
        }
        first_hit = next((i for i, p in enumerate(proba) if float(p) >= 0.5), None)
        t_end = time.perf_counter()
        timings = {
            "attack_start": t0,
            "first_attack_event": t_gen,
            "first_detection": t_score if first_hit is not None else None,
            "attack_classification": t_end,
            "mitigation": t_score,
            "attack_end": t_end,
            "time_to_detect_ms": round((t_score - t0) * 1000, 3),
            "time_to_classify_ms": round((t_end - t0) * 1000, 3),
            "time_to_mitigate_ms": round((t_score - t0) * 1000, 3),
            "first_detected_index": first_hit,
        }
        result["report"] = render_red_team_report(result)
        from app.red_team.loop import enrich_run

        result = enrich_run(result, rows, proba, timings=timings)
        if persist:
            self._persist(result, payload_rows, contract, graph["edge_table"], agent_events)
        return result

    def replay(self, simulation_id: str, persist: bool = True) -> dict[str, Any]:
        stored = self.get_run(simulation_id)
        return self.execute(self.contract_from_stored(stored), persist=persist)

    def contract_from_stored(self, stored: dict[str, Any]) -> AttackContract:
        fp = stored.get("contract") or {}
        attack_id = fp.get("attack_id") or stored["attack_id"]
        threat = self.registry.get(attack_id)
        variant = self.registry.resolve_variant(attack_id, fp.get("variant_id") or stored.get("variant_id"))
        mutation_raw = fp.get("mutation")
        if mutation_raw:
            mutation = MutationParams.model_validate(mutation_raw)
        else:
            mutation = resolve_mutation(
                self.registry,
                threat.attack_id,
                fp.get("difficulty") or stored.get("difficulty", "MEDIUM"),
                variant.id,
            )
        return AttackContract(
            attack_id=threat.attack_id,
            variant_id=variant.id,
            family=threat.family,
            difficulty=(fp.get("difficulty") or stored.get("difficulty") or "MEDIUM").upper(),
            seed=int(fp.get("seed") or stored.get("seed") or RANDOM_STATE),
            transaction_count=int(fp.get("transaction_count") or stored.get("generated") or stored.get("n") or 100),
            target_population=fp.get("target_population") or stored.get("target_population") or "normal_customers",
            mutation=mutation,
            detection_signals=list(threat.detection_signals),
        )

    def get_run(self, simulation_id: str) -> dict[str, Any]:
        path = SIM_DIR / f"{simulation_id}.json"
        if path.exists():
            return json.loads(path.read_text())
        db = session()
        try:
            row = db.get(RedTeamRun, simulation_id)
            if row is None:
                raise KeyError(simulation_id)
            return {
                "simulation_id": row.id,
                "attack_id": row.attack_id,
                "variant_id": row.variant_id,
                "difficulty": row.difficulty,
                "seed": row.seed,
                "generated": row.n,
                "n": row.n,
                "target_population": row.target_population,
                "metrics": json.loads(row.metrics_json or "{}"),
                "report": row.report_text,
                "contract": json.loads(row.params_json or "{}"),
                "model_version": row.model_version,
            }
        finally:
            db.close()

    def get_graph(self, simulation_id: str) -> dict[str, Any]:
        stored = self.get_run(simulation_id)
        graph = dict(stored.get("graph") or {})
        db = session()
        try:
            edges = db.query(GraphEdge).filter(GraphEdge.run_id == simulation_id).all()
            if edges:
                graph["edge_table"] = [
                    {
                        "src_type": e.src_type,
                        "src_id": e.src_id,
                        "dst_type": e.dst_type,
                        "dst_id": e.dst_id,
                        "relation": e.relation,
                        "weight": e.weight,
                    }
                    for e in edges
                ]
            events = db.query(AgentEvent).filter(AgentEvent.run_id == simulation_id).all()
            if events:
                graph["agent_events"] = [
                    {
                        "transaction_id": e.transaction_id,
                        "agent_id": e.agent_id,
                        "tool": e.tool,
                        "intent": e.intent,
                        "in_scope": bool(e.in_scope),
                        "reason": e.reason,
                    }
                    for e in events[:400]
                ]
        finally:
            db.close()
        if stored.get("agent_events") and "agent_events" not in graph:
            graph["agent_events"] = stored["agent_events"]
        graph.setdefault("nodes", [])
        graph.setdefault("edges", [])
        return graph

    def history(self, limit: int = 200) -> list[dict[str, Any]]:
        items: list[tuple[float, dict[str, Any]]] = []
        seen: set[str] = set()
        if SIM_DIR.exists():
            for path in SIM_DIR.glob("*.json"):
                try:
                    data = json.loads(path.read_text())
                except Exception:
                    continue
                if not data.get("attack_id"):
                    continue
                rec = self._history_from_payload(data)
                items.append((path.stat().st_mtime, rec))
                seen.add(rec["simulation_id"])
        db = session()
        try:
            rows = db.query(RedTeamRun).all()
        finally:
            db.close()
        for row in rows:
            if row.id in seen:
                continue
            items.append((0.0, self._history_from_db(row)))
        items.sort(key=lambda pair: pair[0], reverse=True)
        return [rec for _, rec in items[:limit]]

    def weaknesses(self, model_version: str, limit: int = 6) -> list[dict[str, Any]]:
        hist = self.history(limit=500)
        current = [row for row in hist if row.get("model_version") == model_version]
        source = current or hist
        best: dict[str, dict[str, Any]] = {}
        for row in source:
            prev = best.get(row["attack_id"])
            if prev is None or float(row.get("attack_success") or 0) > float(prev.get("attack_success") or 0):
                best[row["attack_id"]] = row
        ranked = sorted(best.values(), key=lambda row: -float(row.get("attack_success") or 0))
        return [row for row in ranked if row.get("detection_rate") is not None][:limit]

    def _history_from_payload(self, data: dict[str, Any]) -> dict[str, Any]:
        metrics = data.get("metrics") or {}
        fidelity = data.get("fidelity") if isinstance(data.get("fidelity"), dict) else {}
        if not fidelity and isinstance(metrics.get("fidelity"), dict):
            fidelity = metrics["fidelity"]
        det = float(metrics.get("detection_rate") or metrics.get("recall") or data.get("detection_rate") or 0.0)
        attack_id = str(data.get("attack_id") or "")
        name = str(data.get("attack_name") or attack_id)
        novelty = ""
        try:
            threat = self.registry.get(attack_id)
            name = threat.name
            novelty = threat.category
        except KeyError:
            pass
        return {
            "simulation_id": str(data.get("simulation_id") or ""),
            "attack_id": attack_id,
            "attack_name": name,
            "variant_id": str(data.get("variant_id") or ""),
            "difficulty": str(data.get("difficulty") or ""),
            "seed": int(data.get("seed") or 0),
            "scale": int(data.get("generated") or data.get("n") or 0),
            "model_version": str(data.get("model_version") or ""),
            "detection_rate": det,
            "attack_success": float(metrics.get("attack_success_rate") or (1.0 - det)),
            "precision": float(metrics.get("precision") or 0.0),
            "recall": float(metrics.get("recall") or 0.0),
            "f1": float(metrics.get("f1") or 0.0),
            "pr_auc": float(metrics.get("pr_auc") or 0.0),
            "fpr": float(metrics.get("fpr") or 0.0),
            "fidelity": float(fidelity.get("overall_fidelity") or 0.0),
            "novelty": novelty,
        }

    def _history_from_db(self, row: RedTeamRun) -> dict[str, Any]:
        metrics = json.loads(row.metrics_json or "{}")
        payload = {
            "simulation_id": row.id,
            "attack_id": row.attack_id,
            "attack_name": row.attack_id,
            "variant_id": row.variant_id,
            "difficulty": row.difficulty,
            "seed": row.seed,
            "generated": row.n,
            "model_version": row.model_version,
            "metrics": metrics,
            "fidelity": metrics.get("fidelity") if isinstance(metrics.get("fidelity"), dict) else {},
        }
        return self._history_from_payload(payload)

    def _pick_board_run(self, runs: list[RedTeamRun], prefix: str) -> RedTeamRun:
        matched = [row for row in runs if prefix and str(row.model_version or "").startswith(prefix)]
        pool = matched or list(runs)
        if prefix:
            medium = [row for row in pool if str(row.difficulty or "").upper() == "MEDIUM"]
            if medium:
                return medium[-1]
        return pool[-1]

    def leaderboard(self, prefer_model: str | None = None) -> list[dict[str, Any]]:
        db = session()
        try:
            rows = db.query(RedTeamRun).all()
        finally:
            db.close()
        by_attack: dict[str, list[RedTeamRun]] = {}
        for row in rows:
            by_attack.setdefault(row.attack_id, []).append(row)
        prefix = (prefer_model or "").split("-hist")[0]
        board = []
        for threat in self.registry.list():
            runs = by_attack.get(threat.attack_id, [])
            if runs:
                latest = self._pick_board_run(runs, prefix)
                metrics = json.loads(latest.metrics_json or "{}")
                det = float(metrics.get("detection_rate") if metrics.get("detection_rate") is not None else 0.0)
                fidelity = metrics.get("fidelity") if isinstance(metrics.get("fidelity"), dict) else {}
                board.append(
                    {
                        "attack_id": threat.attack_id,
                        "name": threat.name,
                        "family": threat.family,
                        "difficulty": latest.difficulty,
                        "detection_rate": det,
                        "attack_success": float(metrics.get("attack_success_rate") or (1.0 - det)),
                        "evasion": 1.0 - det,
                        "pr_auc": float(metrics.get("pr_auc") or 0.0),
                        "precision": float(metrics.get("precision") or 0.0),
                        "recall": float(metrics.get("recall") or 0.0),
                        "f1": float(metrics.get("f1") or 0.0),
                        "fpr": float(metrics.get("fpr") or 0.0),
                        "fidelity": float(fidelity.get("overall_fidelity") or 0.0),
                        "scale": latest.n,
                        "novelty": threat.category,
                        "model_version": latest.model_version,
                    }
                )
            else:
                board.append(
                    {
                        "attack_id": threat.attack_id,
                        "name": threat.name,
                        "family": threat.family,
                        "difficulty": "—",
                        "detection_rate": None,
                        "attack_success": None,
                        "evasion": None,
                        "pr_auc": None,
                        "precision": None,
                        "recall": None,
                        "f1": None,
                        "fpr": None,
                        "fidelity": None,
                        "scale": 0,
                        "novelty": threat.category,
                        "model_version": None,
                    }
                )
        board.sort(key=lambda r: (-(r["evasion"] or -1), r["name"]))
        return board

    def _persist(
        self,
        result: dict[str, Any],
        payload_rows: list[dict[str, Any]],
        contract: AttackContract,
        edges: list[dict[str, Any]],
        agent_events: list[dict[str, Any]],
    ) -> None:
        (SIM_DIR / f"{result['simulation_id']}.json").write_text(json.dumps(result, default=str))
        db = session()
        try:
            db.add(
                RedTeamRun(
                    id=result["simulation_id"],
                    attack_id=contract.attack_id,
                    variant_id=contract.variant_id,
                    family=contract.family,
                    difficulty=contract.difficulty,
                    n=contract.transaction_count,
                    seed=contract.seed,
                    target_population=contract.target_population,
                    params_json=json.dumps(contract.fingerprint()),
                    metrics_json=json.dumps({**result["metrics"], "fidelity": result["fidelity"]}, default=str),
                    report_text=result["report"],
                    model_version=result["model_version"],
                )
            )
            for rec in payload_rows[:400]:
                db.add(
                    PaymentRow(
                        run_id=result["simulation_id"],
                        transaction_id=str(rec["transaction_id"]),
                        attack_family=contract.family,
                        amount=float(rec.get("amount") or 0),
                        fraud_probability=float(rec.get("fraud_probability") or 0),
                        decision=str(rec.get("decision") or "ALLOW"),
                        payload=json.dumps({k: rec[k] for k in rec if k != "explanation"}, default=str),
                    )
                )
            for edge in edges[:4000]:
                db.add(
                    GraphEdge(
                        run_id=result["simulation_id"],
                        src_type=str(edge["src_type"]),
                        src_id=str(edge["src_id"])[:64],
                        dst_type=str(edge["dst_type"]),
                        dst_id=str(edge["dst_id"])[:64],
                        relation=str(edge["relation"]),
                        weight=float(edge.get("weight") or 1.0),
                    )
                )
            for event in agent_events[:400]:
                db.add(
                    AgentEvent(
                        run_id=result["simulation_id"],
                        transaction_id=str(event.get("transaction_id") or ""),
                        agent_id=str(event.get("agent_id") or ""),
                        tool=str(event.get("tool") or ""),
                        intent=str(event.get("intent") or "")[:64],
                        in_scope=1 if event.get("in_scope") else 0,
                        reason=str(event.get("reason") or ""),
                    )
                )
            db.commit()
        finally:
            db.close()
