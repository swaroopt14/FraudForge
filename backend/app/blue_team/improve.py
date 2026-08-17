"""Closed-loop Blue improvement. Same seed before vs after. Never writes BLUE-0.1.0."""

from __future__ import annotations

import json
from typing import Any

import numpy as np
import pandas as pd

from app.core.config import FEATURE_COLUMNS_V012, FEATURE_VERSION_V012, MODELS_DIR, REPORTS_DIR, ensure_dirs
from app.core.model_registry import REGISTRY_PATH, assert_frozen_blue, load_registry, sha256_file
from app.evaluation.coverage import generate_fixed_family_attacks
from app.fraud.pipeline import BlueTeam, prepare_split_balanced
from app.redteam.controller import RedTeamController
from app.threats.registry import get_registry

IMPROVED_ID = "BLUE-0.1.3"
IMPROVED_DIR = MODELS_DIR / IMPROVED_ID
IMPROVED_ARTIFACT = IMPROVED_DIR / "blue_team.joblib"
LAST_LOOP_PATH = REPORTS_DIR / "last_loop.json"


def _round_view(result: dict[str, Any]) -> dict[str, Any]:
    metrics = result.get("metrics") or {}
    generated = int(result.get("generated") or 0)
    detected = int(result.get("detected") or 0)
    missed = int(result.get("missed") or max(0, generated - detected))
    detection = float(result.get("detection_rate") or 0.0)
    bypass = float(metrics.get("attack_success_rate") if metrics.get("attack_success_rate") is not None else 1.0 - detection)
    return {
        "simulation_id": result.get("simulation_id"),
        "attack_id": result.get("attack_id"),
        "attack_name": result.get("attack_name"),
        "variant_id": result.get("variant_id"),
        "difficulty": result.get("difficulty"),
        "seed": result.get("seed"),
        "scale": generated,
        "generated": generated,
        "detected": detected,
        "missed": missed,
        "detection_rate": detection,
        "attack_success": bypass,
        "precision": float(metrics.get("precision") or 0.0),
        "recall": detection,
        "f1": float(metrics.get("f1") or 0.0),
        "model_version": result.get("model_version"),
        "finding": result.get("finding"),
    }


def _delta(before: dict[str, Any], after: dict[str, Any]) -> dict[str, float]:
    def lift(key: str) -> float:
        return float(after.get(key) or 0.0) - float(before.get(key) or 0.0)

    return {
        "detection_rate": lift("detection_rate"),
        "attack_success": lift("attack_success"),
        "detected": float(after.get("detected") or 0) - float(before.get("detected") or 0),
        "missed": float(after.get("missed") or 0) - float(before.get("missed") or 0),
    }


def train_improved(
    payments: pd.DataFrame,
    *,
    attack_id: str,
    variant_id: str,
    difficulty: str,
    family: str,
    n_each: int = 48,
    n_focus: int = 240,
    persist: bool = True,
) -> BlueTeam:
    """Train BLUE-0.1.3 on the library plus extra copies of the family that just evaded."""
    from app.blue_team.train import _known_variant_overlays

    assert_frozen_blue()
    attacks = generate_fixed_family_attacks(payments, n_each=n_each, seed=13)
    focus = _known_variant_overlays(
        payments,
        [
            (attack_id, variant_id, difficulty, family),
            (attack_id, variant_id, "MEDIUM", family),
        ],
        n=max(n_focus, n_each),
        seed=19,
    )
    attacks = pd.concat([attacks, focus], ignore_index=True)
    train, test = prepare_split_balanced(payments, attacks, seed=424242)
    blue = BlueTeam(feature_names=list(FEATURE_COLUMNS_V012), model_id=IMPROVED_ID)
    blue.train(train, test, calibrate=True)
    if persist:
        IMPROVED_DIR.mkdir(parents=True, exist_ok=True)
        blue.save(IMPROVED_ARTIFACT)
        _register_improved()
    return blue


def _register_improved() -> None:
    reg = load_registry()
    blue = reg.setdefault("blue_team", {})
    blue["fraud_detector_v013"] = {
        "version": IMPROVED_ID,
        "status": "candidate",
        "objective": "Round-2 detector trained on the closed-loop miss; does not replace BLUE-0.1.0 or overwrite 0.1.2 by default",
        "artifact": f"models/{IMPROVED_ID}/blue_team.joblib",
        "feature_version": FEATURE_VERSION_V012,
    }
    REGISTRY_PATH.write_text(json.dumps(reg, indent=2) + "\n")


def run_closed_loop(
    payments: pd.DataFrame,
    before_team: BlueTeam,
    *,
    attack_id: str = "BEN-001",
    variant_id: str | None = "BEN-V05",
    difficulty: str = "HIGH",
    transaction_count: int = 400,
    seed: int = 424242,
    persist: bool = True,
    n_each: int = 48,
    n_focus: int = 240,
) -> dict[str, Any]:
    """Round 1 live detector → retrain BLUE-0.1.3 → Round 2 same seed."""
    assert_frozen_blue()
    registry = get_registry()
    threat = registry.get(attack_id)
    variant = registry.resolve_variant(attack_id, variant_id)
    red_before = RedTeamController(payments, before_team, registry)
    before_run = red_before.run(
        attack_id,
        variant_id=variant.id,
        difficulty=difficulty,
        transaction_count=transaction_count,
        seed=seed,
        persist=persist,
        explain=False,
    )
    after_team = train_improved(
        payments,
        attack_id=attack_id,
        variant_id=variant.id,
        difficulty=difficulty,
        family=threat.family,
        n_each=n_each,
        n_focus=n_focus,
        persist=persist,
    )
    red_after = RedTeamController(payments, after_team, registry)
    after_run = red_after.run(
        attack_id,
        variant_id=variant.id,
        difficulty=difficulty,
        transaction_count=transaction_count,
        seed=seed,
        persist=persist,
        explain=False,
    )
    before = _round_view(before_run)
    after = _round_view(after_run)
    report = {
        "contract": {
            "attack_id": attack_id,
            "variant_id": variant.id,
            "variant_name": variant.name,
            "family": threat.family,
            "difficulty": difficulty.upper(),
            "seed": seed,
            "transaction_count": transaction_count,
        },
        "before": before,
        "after": after,
        "delta": _delta(before, after),
        "before_model": before_team.version() if hasattr(before_team, "version") else before.get("model_version"),
        "after_model": after_team.version() if hasattr(after_team, "version") else after.get("model_version"),
        "artifact": str(IMPROVED_ARTIFACT),
        "frozen_blue_sha256": sha256_file(MODELS_DIR / "BLUE-0.1.0" / "blue_team.joblib"),
        "note": "Same attack, same seed. Round 1 is the live detector. Round 2 is BLUE-0.1.3 trained on that miss. Frozen BLUE-0.1.0 is unchanged.",
    }
    if persist:
        ensure_dirs()
        LAST_LOOP_PATH.parent.mkdir(parents=True, exist_ok=True)
        LAST_LOOP_PATH.write_text(json.dumps(report, indent=2, default=str) + "\n")
    return report


def load_last_loop() -> dict[str, Any] | None:
    if not LAST_LOOP_PATH.exists():
        return None
    try:
        return json.loads(LAST_LOOP_PATH.read_text())
    except json.JSONDecodeError:
        return None
