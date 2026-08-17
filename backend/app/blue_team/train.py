"""Train BLUE-0.1.1 detector + classifier. Never writes models/BLUE-0.1.0/."""

from __future__ import annotations

import json
from typing import Any

import numpy as np
import pandas as pd

from app.blue_team.classifiers.attack_classifier import train_from_variants
from app.core.config import (
    FEATURE_COLUMNS_V011,
    FEATURE_COLUMNS_V012,
    FEATURE_COLUMNS_V020,
    FEATURE_VERSION_V011,
    FEATURE_VERSION_V012,
    FEATURE_VERSION_V020,
    MODELS_DIR,
)
from app.core.model_registry import REGISTRY_PATH, assert_frozen_blue, load_registry, sha256_file
from app.data.history import CorpusHistory
from app.evaluation.coverage import compare_coverage, generate_fixed_family_attacks
from app.fraud.pipeline import BlueTeam, prepare_split_balanced
from app.redteam.difficulty import resolve_mutation
from app.redteam.mutations import apply_mutation
from app.simulation.legit import fit_profiles, generate_legitimate
from app.threats.registry import get_registry

V011_DIR = MODELS_DIR / "BLUE-0.1.1"
V011_ARTIFACT = V011_DIR / "blue_team.joblib"
V012_DIR = MODELS_DIR / "BLUE-0.1.2"
V012_ARTIFACT = V012_DIR / "blue_team.joblib"
V020_DIR = MODELS_DIR / "BLUE-0.2.0"
V020_ARTIFACT = V020_DIR / "blue_team.joblib"


def train_blue_011(
    payments: pd.DataFrame,
    *,
    n_each: int = 80,
    persist: bool = True,
) -> dict[str, Any]:
    assert_frozen_blue()
    attacks = generate_fixed_family_attacks(payments, n_each=n_each, seed=11)
    train, test = prepare_split_balanced(payments, attacks, seed=424242)
    blue = BlueTeam(feature_names=list(FEATURE_COLUMNS_V011), model_id="BLUE-0.1.1")
    metrics = blue.train(train, test, calibrate=True)
    families_train = sorted(f for f in train.loc[train["fraud_label"] == 1, "attack_family"].dropna().unique().tolist() if f)
    families_test = sorted(f for f in test.loc[test["fraud_label"] == 1, "attack_family"].dropna().unique().tolist() if f)
    metrics["families_in_train"] = families_train
    metrics["families_in_test"] = families_test
    clf = train_from_variants(payments, get_registry(), n_each=24)
    coverage = None
    if persist:
        V011_DIR.mkdir(parents=True, exist_ok=True)
        blue.save(V011_ARTIFACT)
        _register_v011()
        coverage = compare_coverage(payments, n_each=min(n_each, 80), persist=True)
    return {
        "model_id": "BLUE-0.1.1",
        "feature_version": FEATURE_VERSION_V011,
        "artifact": str(V011_ARTIFACT),
        "metrics": metrics,
        "classifier_version": clf.version,
        "classifier_fitted": clf.fitted,
        "classifier_classes": clf.classes_,
        "coverage": coverage,
        "frozen_blue_sha256": sha256_file(MODELS_DIR / "BLUE-0.1.0" / "blue_team.joblib"),
    }


def _register_v011() -> None:
    reg = load_registry()
    blue = reg.setdefault("blue_team", {})
    blue["fraud_detector_v011"] = {
        "version": "BLUE-0.1.1",
        "status": "experimental",
        "objective": "P(fraud) from P1 behavioral features; calibrated risk 0–100",
        "artifact": "models/BLUE-0.1.1/blue_team.joblib",
        "feature_version": FEATURE_VERSION_V011,
    }
    blue["attack_classifier"] = {
        **(blue.get("attack_classifier") or {}),
        "v011": {
            "version": "BLUE-CLS-0.1.1",
            "status": "experimental",
            "objective": "attack family + variant or UNKNOWN/EMERGING",
            "artifact": "models/BLUE-CLS-0.1.1/attack_classifier.joblib",
        },
    }
    REGISTRY_PATH.write_text(json.dumps(reg, indent=2) + "\n")


def _known_variant_overlays(
    payments: pd.DataFrame,
    specs: list[tuple[str, str, str, str]],
    *,
    n: int,
    seed: int,
) -> pd.DataFrame:
    """Extra Round-1 examples of known variants. Quiet HIGH variants stay out of this mix."""
    registry = get_registry()
    profiles = fit_profiles(payments)
    history = CorpusHistory.from_payments(payments)
    frames: list[pd.DataFrame] = []
    for i, (attack_id, variant_id, difficulty, family) in enumerate(specs):
        mutation = resolve_mutation(registry, attack_id, difficulty, variant_id)
        base = generate_legitimate(profiles, n, seed=seed + i, source=payments)
        rng = np.random.default_rng(seed + i)
        rows = apply_mutation(base, mutation, rng, family)
        rows = history.attach(rows, refresh_concentration=False)
        from app.blue_team.context import attach_p2_features

        rows = attach_p2_features(rows)
        rows["attack_id"] = attack_id
        rows["variant_id"] = variant_id
        frames.append(rows)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def train_blue_012(
    payments: pd.DataFrame,
    *,
    n_each: int = 80,
    persist: bool = True,
) -> dict[str, Any]:
    """Round-1 demo detector. Never writes BLUE-0.1.0."""
    assert_frozen_blue()
    attacks = generate_fixed_family_attacks(payments, n_each=n_each, seed=11)
    extras = _known_variant_overlays(
        payments,
        [
            ("BEN-001", "BEN-V01", "MEDIUM", "beneficiary_anomaly"),
            ("BEN-001", "BEN-V01", "LOW", "beneficiary_anomaly"),
            ("MUL-001", "MUL-V01", "MEDIUM", "mule_network"),
        ],
        n=max(320, n_each),
        seed=17,
    )
    attacks = pd.concat([attacks, extras], ignore_index=True)
    train, test = prepare_split_balanced(payments, attacks, seed=424242)
    blue = BlueTeam(feature_names=list(FEATURE_COLUMNS_V012), model_id="BLUE-0.1.2")
    metrics = blue.train(train, test, calibrate=True)
    families_train = sorted(f for f in train.loc[train["fraud_label"] == 1, "attack_family"].dropna().unique().tolist() if f)
    families_test = sorted(f for f in test.loc[test["fraud_label"] == 1, "attack_family"].dropna().unique().tolist() if f)
    metrics["families_in_train"] = families_train
    metrics["families_in_test"] = families_test
    clf = train_from_variants(payments, get_registry(), n_each=24)
    coverage = None
    if persist:
        V012_DIR.mkdir(parents=True, exist_ok=True)
        blue.save(V012_ARTIFACT)
        _register_v012()
        coverage = compare_coverage(payments, n_each=min(n_each, 80), persist=True)
    return {
        "model_id": "BLUE-0.1.2",
        "feature_version": FEATURE_VERSION_V012,
        "artifact": str(V012_ARTIFACT),
        "metrics": metrics,
        "classifier_version": clf.version,
        "classifier_fitted": clf.fitted,
        "classifier_classes": clf.classes_,
        "coverage": coverage,
        "frozen_blue_sha256": sha256_file(MODELS_DIR / "BLUE-0.1.0" / "blue_team.joblib"),
    }


def _register_v012() -> None:
    reg = load_registry()
    blue = reg.setdefault("blue_team", {})
    fd = blue.setdefault("fraud_detector", {})
    fd["status"] = "frozen"
    blue["fraud_detector_v012"] = {
        "version": "BLUE-0.1.2",
        "status": "active",
        "objective": "P(fraud) with corpus-grounded beneficiary behavior; Round 1 demo baseline",
        "artifact": "models/BLUE-0.1.2/blue_team.joblib",
        "feature_version": FEATURE_VERSION_V012,
    }
    blue["attack_classifier"] = {
        **(blue.get("attack_classifier") or {}),
        "v012": {
            "version": "BLUE-CLS-0.1.2",
            "status": "experimental",
            "objective": "attack family + variant or UNKNOWN/EMERGING",
            "artifact": "models/BLUE-CLS-0.1.2/attack_classifier.joblib",
        },
    }
    REGISTRY_PATH.write_text(json.dumps(reg, indent=2) + "\n")


def train_blue_020(
    payments: pd.DataFrame,
    *,
    n_each: int = 80,
    persist: bool = True,
) -> dict[str, Any]:
    """P2 detector: P1 features + geo/device/IP/beneficiary graph scores. Never writes BLUE-0.1.0."""
    from app.blue_team.classifiers.attack_classifier import train_from_variants_v020
    from app.evaluation.coverage import compare_p1_vs_p2, generate_p2_context_attacks

    assert_frozen_blue()
    attacks = generate_fixed_family_attacks(payments, n_each=n_each, seed=11)
    extras = _known_variant_overlays(
        payments,
        [
            ("BEN-001", "BEN-V01", "MEDIUM", "beneficiary_anomaly"),
            ("BEN-001", "BEN-N02", "MEDIUM", "beneficiary_anomaly"),
            ("MUL-001", "MUL-V01", "MEDIUM", "mule_network"),
            ("MUL-001", "MUL-N01", "MEDIUM", "mule_network"),
            ("DEV-001", "DEV-N01", "MEDIUM", "shared_device"),
            ("IP-001", "IP-N01", "MEDIUM", "shared_ip"),
            ("GEO-001", "GEO-N01", "MEDIUM", "geo_anomaly"),
        ],
        n=max(240, n_each),
        seed=19,
    )
    context = generate_p2_context_attacks(payments, n_each=max(60, n_each // 2), seed=23)
    attacks = pd.concat([attacks, extras, context], ignore_index=True)
    train, test = prepare_split_balanced(payments, attacks, seed=424242)
    blue = BlueTeam(feature_names=list(FEATURE_COLUMNS_V020), model_id="BLUE-0.2.0")
    metrics = blue.train(train, test, calibrate=True)
    families_train = sorted(f for f in train.loc[train["fraud_label"] == 1, "attack_family"].dropna().unique().tolist() if f)
    families_test = sorted(f for f in test.loc[test["fraud_label"] == 1, "attack_family"].dropna().unique().tolist() if f)
    metrics["families_in_train"] = families_train
    metrics["families_in_test"] = families_test
    clf = train_from_variants_v020(payments, get_registry(), n_each=20)
    coverage = None
    comparison = None
    if persist:
        V020_DIR.mkdir(parents=True, exist_ok=True)
        blue.save(V020_ARTIFACT)
        _register_v020()
        coverage = compare_coverage(payments, n_each=min(n_each, 80), persist=True)
        comparison = compare_p1_vs_p2(payments, n_each=min(n_each, 80), persist=True)
    return {
        "model_id": "BLUE-0.2.0",
        "feature_version": FEATURE_VERSION_V020,
        "artifact": str(V020_ARTIFACT),
        "metrics": metrics,
        "classifier_version": clf.version,
        "classifier_fitted": clf.fitted,
        "classifier_classes": clf.classes_,
        "coverage": coverage,
        "p1_vs_p2": comparison,
        "frozen_blue_sha256": sha256_file(MODELS_DIR / "BLUE-0.1.0" / "blue_team.joblib"),
    }


def _register_v020() -> None:
    reg = load_registry()
    blue = reg.setdefault("blue_team", {})
    fd = blue.setdefault("fraud_detector", {})
    fd["status"] = "frozen"
    blue["fraud_detector_v020"] = {
        "version": "BLUE-0.2.0",
        "status": "candidate",
        "objective": "P(fraud) from P1 behavior plus geo/device/IP/beneficiary graph features",
        "artifact": "models/BLUE-0.2.0/blue_team.joblib",
        "feature_version": FEATURE_VERSION_V020,
    }
    blue["attack_classifier"] = {
        **(blue.get("attack_classifier") or {}),
        "v020": {
            "version": "BLUE-CLS-0.2.0",
            "status": "experimental",
            "objective": "attack family + variant or UNKNOWN/EMERGING on P2 features",
            "artifact": "models/BLUE-CLS-0.2.0/attack_classifier.joblib",
        },
    }
    REGISTRY_PATH.write_text(json.dumps(reg, indent=2) + "\n")
