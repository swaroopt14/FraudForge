"""Score attack configurations. This is not a fraud detector."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import joblib
import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor

from app.core.config import MODELS_DIR, SIM_DIR, ensure_dirs
from app.threats.registry import get_registry

VERSION = "RED-0.1.0"
ARTIFACT = MODELS_DIR / VERSION / "attack_strategy.joblib"

# Families BLUE-0.1.0 already catches vs families it misses. Red-team prior only.
_CAUGHT = {"account_takeover", "velocity_attack", "amount_anomaly"}
_MISSED = {"beneficiary_anomaly", "mule_network", "low_and_slow", "geo_anomaly", "agent_scope", "intent_mismatch"}
_DIFF = {"LOW": 0.30, "MEDIUM": 0.65, "HIGH": 0.90, "ADAPTIVE": 0.75}

FEATURE_NAMES = [
    "difficulty_code",
    "beneficiary_change",
    "amount_deviation",
    "velocity_deviation",
    "device_change",
    "geo_deviation",
    "dest_concentration",
    "share_beneficiary",
    "cluster_count",
    "known_caught_family",
    "known_missed_family",
    "n_signals",
    "available_network_features",
    "available_geo_features",
    "available_intent_features",
    "available_agent_features",
]


def _difficulty_code(level: str) -> float:
    return {"LOW": 0.0, "MEDIUM": 0.5, "HIGH": 1.0, "ADAPTIVE": 0.7}.get((level or "MEDIUM").upper(), 0.5)


def opportunity_vector(threat, mutation, difficulty: str) -> list[float]:
    m = mutation.model_dump() if hasattr(mutation, "model_dump") else dict(mutation)
    family = str(getattr(threat, "family", "") or "")
    return [
        _difficulty_code(difficulty),
        float(m.get("beneficiary_change_probability") or 0.0),
        float(m.get("amount_deviation") or 0.0),
        abs(float(m.get("velocity_multiplier") or 1.0) - 1.0),
        float(m.get("device_change_probability") or 0.0),
        float(m.get("geo_deviation") or 0.0),
        float(m.get("dest_concentration_delta") or 0.0),
        1.0 if m.get("share_beneficiary") else 0.0,
        float(m.get("cluster_count") or 1),
        1.0 if family in _CAUGHT else 0.0,
        1.0 if family in _MISSED else 0.0,
        float(len(getattr(threat, "detection_signals", []) or [])),
        0.0,
        0.0,
        0.0,
        0.0,
    ]


def heuristic_success(family: str, difficulty: str) -> float:
    """Prior from BLUE-0.1.0 diagnostics. Not a Blue-Team label."""
    base = 0.12 if family in _CAUGHT else 0.55
    if family in _MISSED:
        base = 0.92
    bump = {"LOW": -0.08, "MEDIUM": 0.0, "HIGH": 0.06, "ADAPTIVE": 0.03}.get((difficulty or "MEDIUM").upper(), 0.0)
    return float(min(0.999, max(0.001, base + bump)))


def strategy_payload(threat, variant, difficulty: str, mutation, expected_success: float) -> dict[str, Any]:
    m = mutation.model_dump() if hasattr(mutation, "model_dump") else dict(mutation)
    return {
        "attack_id": threat.attack_id,
        "attack_family": threat.family,
        "attack_name": threat.name,
        "variant_id": variant.id,
        "target_surface": (threat.attack_surface or ["payment"])[0],
        "difficulty": difficulty.lower(),
        "mutation_strategy": {
            "beneficiary_change": float(m.get("beneficiary_change_probability") or 0.0),
            "amount_deviation": float(m.get("amount_deviation") or 0.0),
            "velocity_deviation": abs(float(m.get("velocity_multiplier") or 1.0) - 1.0),
            "device_change": float(m.get("device_change_probability") or 0.0),
            "geo_deviation": float(m.get("geo_deviation") or 0.0),
        },
        "network_strategy": {
            "shared_beneficiary": bool(m.get("share_beneficiary")),
            "fan_in_target": int(m.get("cluster_count") or 1),
            "cluster_size": int(m.get("cluster_count") or 1),
            "timing_variation": abs(float(m.get("hour_shift") or 0.0)) / 24.0,
        },
        "evasion_strategy": list(threat.evasion_strategies or []),
        "expected_goal": "maximize_blue_team_evasion",
        "expected_attack_success": float(expected_success),
        "model_version": VERSION,
    }


class RedTeamAttackIntelligence:
    """Predicts expected attack success for a configuration. Never outputs P(fraud)."""

    def __init__(self) -> None:
        self.model: HistGradientBoostingRegressor | None = None
        self.feature_names = list(FEATURE_NAMES)
        self.version = VERSION
        self.fitted = False

    def _history_xy(self) -> tuple[np.ndarray, np.ndarray]:
        registry = get_registry()
        xs: list[list[float]] = []
        ys: list[float] = []
        if SIM_DIR.exists():
            for path in SIM_DIR.glob("*.json"):
                try:
                    data = json.loads(path.read_text())
                except Exception:
                    continue
                attack_id = data.get("attack_id")
                if not attack_id:
                    continue
                try:
                    threat = registry.get(str(attack_id))
                except KeyError:
                    continue
                mutation = (data.get("contract") or {}).get("mutation") or {}
                difficulty = str(data.get("difficulty") or "MEDIUM")
                xs.append(opportunity_vector(threat, mutation, difficulty))
                metrics = data.get("metrics") or {}
                ys.append(float(metrics.get("attack_success_rate") or (1.0 - float(data.get("detection_rate") or 0.0))))
        return (np.asarray(xs, dtype=float), np.asarray(ys, dtype=float)) if xs else (np.zeros((0, len(FEATURE_NAMES))), np.zeros((0,)))

    def fit(self, x: np.ndarray | None = None, y: np.ndarray | None = None) -> "RedTeamAttackIntelligence":
        if x is None or y is None:
            x, y = self._history_xy()
        if len(y) < 8:
            self.fitted = False
            self.model = None
            return self
        self.model = HistGradientBoostingRegressor(max_depth=4, max_iter=80, random_state=7)
        self.model.fit(x, y)
        self.fitted = True
        return self

    def predict_success(self, vector: list[float], family: str, difficulty: str) -> float:
        prior = heuristic_success(family, difficulty)
        if self.model is None or not self.fitted:
            return prior
        pred = float(self.model.predict(np.asarray([vector], dtype=float))[0])
        return float(min(0.999, max(0.001, 0.5 * pred + 0.5 * prior)))

    def recommend(self, *, n: int = 3, recent_ids: list[str] | None = None) -> dict[str, Any]:
        from app.red_team.models.evaluator import red_objective
        from app.red_team.models.novelty import RedTeamNoveltyModel

        registry = get_registry()
        novelty = RedTeamNoveltyModel()
        recent = set(recent_ids or [])
        ranked = []
        for threat in registry.list():
            for variant in threat.variants:
                for difficulty in ("LOW", "MEDIUM", "HIGH"):
                    mutation = registry.mutation(threat.attack_id, difficulty, variant.id)
                    vec = opportunity_vector(threat, mutation, difficulty)
                    success = self.predict_success(vec, threat.family, difficulty)
                    nov = novelty.score_threat(threat, mutation)
                    diversity = 0.0 if threat.attack_id in recent else 1.0
                    utility = red_objective(
                        success=success,
                        fidelity=0.8,
                        novelty=nov["novelty_score"] / 100.0,
                        difficulty=_DIFF.get(difficulty, 0.5),
                        diversity=diversity,
                    )
                    ranked.append(
                        {
                            "utility": utility,
                            "strategy": strategy_payload(threat, variant, difficulty, mutation, success),
                            "novelty": nov,
                        }
                    )
        ranked.sort(key=lambda row: -row["utility"])
        best = ranked[: max(1, n)]
        return {
            "model_version": self.version,
            "objective": "What attack strategy should I test next?",
            "not": "fraud_probability",
            "recommendation": best[0]["strategy"],
            "alternatives": [row["strategy"] for row in best[1:]],
            "novelty": best[0]["novelty"],
        }

    def save(self, path: Path | None = None) -> Path:
        ensure_dirs()
        dest = path or ARTIFACT
        dest.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump({"model": self.model, "fitted": self.fitted, "feature_names": self.feature_names, "version": self.version}, dest)
        (dest.parent / "VERSION.json").write_text(json.dumps({"model_version": self.version, "fitted": self.fitted}, indent=2))
        return dest

    @classmethod
    def load(cls, path: Path | None = None) -> "RedTeamAttackIntelligence":
        inst = cls()
        src = path or ARTIFACT
        if not src.exists():
            return inst.fit()
        blob = joblib.load(src)
        inst.model = blob.get("model")
        inst.fitted = bool(blob.get("fitted"))
        inst.feature_names = list(blob.get("feature_names") or FEATURE_NAMES)
        return inst
