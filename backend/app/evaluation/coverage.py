"""Fixed-seed attack coverage: generated / detected / classified / recall per family."""

from __future__ import annotations

import json
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import f1_score

from app.core.config import EVAL_DIR, MODELS_DIR, RANDOM_STATE, ensure_dirs
from app.core.model_registry import FROZEN_BLUE
from app.fraud.pipeline import BlueTeam, compute_metrics
from app.redteam.difficulty import resolve_mutation
from app.redteam.mutations import apply_mutation
from app.simulation.legit import fit_profiles, generate_legitimate
from app.threats.registry import get_registry

COVERAGE_SEED = 7
COVERAGE_PATH = EVAL_DIR / "benchmarks" / "p1" / "attack_coverage.json"

ENGINEERING_TARGETS = {
    "binary_recall": 0.85,
    "binary_precision": 0.85,
    "binary_f1": 0.85,
    "binary_pr_auc": 0.90,
    "binary_fpr": 0.02,
    "macro_f1": 0.75,
    "per_family_recall": 0.70,
    "note": "Engineering targets, not measured claims.",
}


def generate_fixed_family_attacks(
    payments: pd.DataFrame,
    n_each: int = 80,
    seed: int = COVERAGE_SEED,
    difficulty: str = "MEDIUM",
) -> pd.DataFrame:
    registry = get_registry()
    profiles = fit_profiles(payments)
    from app.data.history import CorpusHistory

    history = CorpusHistory.from_payments(payments)
    frames = []
    for i, threat in enumerate(registry.list()):
        mutation = resolve_mutation(registry, threat.attack_id, difficulty, None)
        base = generate_legitimate(profiles, n_each, seed=seed + i, history=history, source=payments)
        rng = np.random.default_rng(seed + i)
        rows = apply_mutation(base, mutation, rng, threat.family)
        rows = history.attach(rows, refresh_concentration=False)
        from app.blue_team.context import attach_p2_features

        rows = attach_p2_features(rows)
        rows["attack_id"] = threat.attack_id
        rows["variant_id"] = threat.variants[0].id
        frames.append(rows)
    return pd.concat(frames, ignore_index=True)


def _family_rows(attacks: pd.DataFrame, team: BlueTeam, classifier=None) -> list[dict[str, Any]]:
    rows = []
    for family, group in attacks.groupby("attack_family", sort=False):
        proba = team.score(group)
        detected_mask = proba >= 0.5
        generated = int(len(group))
        detected = int(detected_mask.sum())
        classified = 0
        if classifier is not None and getattr(classifier, "fitted", False):
            preds = classifier.predict(group, fraud_probability=proba)
            classified = int(sum(1 for p in preds if p.get("family") == family))
        rows.append(
            {
                "family": str(family),
                "attack_id": str(group["attack_id"].iloc[0]) if "attack_id" in group.columns else str(family),
                "generated": generated,
                "detected": detected,
                "classified": classified,
                "recall": float(detected / generated) if generated else 0.0,
                "identification_recall": float(classified / generated) if generated else 0.0,
            }
        )
    return rows


def score_model_coverage(
    payments: pd.DataFrame,
    team: BlueTeam,
    attacks: pd.DataFrame,
    classifier=None,
) -> dict[str, Any]:
    legit = payments.loc[payments["fraud_label"] == 0]
    hold_n = min(len(legit), max(200, len(attacks) // 5))
    hold = legit.sample(hold_n, random_state=RANDOM_STATE) if hold_n else legit
    mix = pd.concat([attacks, hold], ignore_index=True)
    extra = ["attack_id", "variant_id", "seed", "ground_truth", "simulation_id"]
    mix = mix.drop(columns=[c for c in extra if c in mix.columns], errors="ignore")
    binary = compute_metrics(mix["fraud_label"].to_numpy(), team.score(mix))
    family_table = _family_rows(attacks, team, classifier)
    macro = None
    if classifier is not None and getattr(classifier, "fitted", False):
        preds = classifier.predict(attacks, fraud_probability=team.score(attacks))
        y_true = attacks["attack_family"].astype(str).to_numpy()
        y_pred = np.array([p["family"] for p in preds], dtype=object)
        macro = float(f1_score(y_true, y_pred, average="macro", zero_division=0))
    return {
        "model_id": team.model_id,
        "model_version": team.version(),
        "n_features": len(team.feature_names),
        "binary": binary,
        "macro_f1": macro,
        "families": family_table,
    }


def compare_coverage(
    payments: pd.DataFrame,
    n_each: int = 80,
    persist: bool = True,
) -> dict[str, Any]:
    attacks = generate_fixed_family_attacks(payments, n_each=n_each, seed=COVERAGE_SEED)
    baseline = BlueTeam.load(FROZEN_BLUE)
    from app.blue_team.classifiers.attack_classifier import ARTIFACT_V011, ARTIFACT_V012, BlueAttackClassifier

    clf = BlueAttackClassifier.load(ARTIFACT_V012)
    if not clf.fitted:
        clf = BlueAttackClassifier.load(ARTIFACT_V011)
    if not clf.fitted:
        clf = BlueAttackClassifier.load()
    frozen = score_model_coverage(payments, baseline, attacks, classifier=clf if clf.fitted else None)
    candidate = None
    for version in ("BLUE-0.2.0", "BLUE-0.1.2", "BLUE-0.1.1"):
        candidate_path = MODELS_DIR / version / "blue_team.joblib"
        if candidate_path.exists():
            cand_team = BlueTeam.load(candidate_path)
            candidate = score_model_coverage(payments, cand_team, attacks, classifier=clf if clf.fitted else None)
            break
    payload = {
        "seed": COVERAGE_SEED,
        "n_each": n_each,
        "baseline": frozen,
        "candidate": candidate,
        "engineering_targets": ENGINEERING_TARGETS,
        "note": "Same seed and attack configuration for both models. Numbers are measured, not targets.",
    }
    if persist:
        ensure_dirs()
        COVERAGE_PATH.parent.mkdir(parents=True, exist_ok=True)
        COVERAGE_PATH.write_text(json.dumps(payload, indent=2, default=str))
    return payload


def load_coverage() -> dict[str, Any] | None:
    if COVERAGE_PATH.exists():
        return json.loads(COVERAGE_PATH.read_text())
    return None


P2_COMPARE_PATH = EVAL_DIR / "benchmarks" / "p2" / "comparison.json"

P2_CONTEXT_VARIANTS = [
    ("BEN-001", "BEN-N01", "MEDIUM", "beneficiary_anomaly"),
    ("BEN-001", "BEN-N02", "MEDIUM", "beneficiary_anomaly"),
    ("BEN-001", "BEN-N03", "HIGH", "beneficiary_anomaly"),
    ("MUL-001", "MUL-N01", "MEDIUM", "mule_network"),
    ("MUL-001", "MUL-N02", "MEDIUM", "mule_network"),
    ("MUL-001", "MUL-N03", "HIGH", "mule_network"),
    ("DEV-001", "DEV-N01", "MEDIUM", "shared_device"),
    ("DEV-001", "DEV-N02", "HIGH", "shared_device"),
    ("IP-001", "IP-N01", "MEDIUM", "shared_ip"),
    ("IP-001", "IP-N02", "HIGH", "shared_ip"),
    ("GEO-001", "GEO-N01", "MEDIUM", "geo_anomaly"),
    ("GEO-001", "GEO-N02", "MEDIUM", "geo_anomaly"),
    ("GEO-001", "GEO-N03", "HIGH", "geo_anomaly"),
]

LANE_FAMILIES = {
    "network": {"mule_network", "shared_device", "shared_ip", "beneficiary_anomaly", "merchant_coordination"},
    "geo": {"geo_anomaly"},
    "device": {"shared_device"},
    "beneficiary": {"beneficiary_anomaly", "mule_network"},
    "mule": {"mule_network"},
}


def generate_p2_context_attacks(payments: pd.DataFrame, n_each: int = 80, seed: int = COVERAGE_SEED) -> pd.DataFrame:
    registry = get_registry()
    profiles = fit_profiles(payments)
    from app.blue_team.context import attach_p2_features
    from app.data.history import CorpusHistory

    history = CorpusHistory.from_payments(payments)
    frames = []
    for i, (attack_id, variant_id, difficulty, family) in enumerate(P2_CONTEXT_VARIANTS):
        mutation = resolve_mutation(registry, attack_id, difficulty, variant_id)
        base = generate_legitimate(profiles, n_each, seed=seed + 100 + i, history=history, source=payments)
        rng = np.random.default_rng(seed + 100 + i)
        rows = apply_mutation(base, mutation, rng, family)
        rows = history.attach(rows, refresh_concentration=False)
        rows = attach_p2_features(rows)
        rows["attack_id"] = attack_id
        rows["variant_id"] = variant_id
        frames.append(rows)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def _lane_recall(family_table: list[dict[str, Any]], families: set[str]) -> float:
    rows = [r for r in family_table if r.get("family") in families]
    generated = sum(int(r.get("generated") or 0) for r in rows)
    detected = sum(int(r.get("detected") or 0) for r in rows)
    return float(detected / generated) if generated else 0.0


def _context_block(family_table: list[dict[str, Any]]) -> dict[str, float]:
    return {name: _lane_recall(family_table, fams) for name, fams in LANE_FAMILIES.items()}


def compare_p1_vs_p2(payments: pd.DataFrame, n_each: int = 80, persist: bool = True) -> dict[str, Any]:
    """Same seed, same overlays. BLUE-0.1.2 vs BLUE-0.2.0. Numbers are measured."""
    from app.blue_team.classifiers.attack_classifier import ARTIFACT_V012, ARTIFACT_V020, BlueAttackClassifier

    family_attacks = generate_fixed_family_attacks(payments, n_each=n_each, seed=COVERAGE_SEED)
    context_attacks = generate_p2_context_attacks(payments, n_each=n_each, seed=COVERAGE_SEED)
    attacks = pd.concat([family_attacks, context_attacks], ignore_index=True)
    p1_path = MODELS_DIR / "BLUE-0.1.2" / "blue_team.joblib"
    p2_path = MODELS_DIR / "BLUE-0.2.0" / "blue_team.joblib"
    if not p1_path.exists() or not p2_path.exists():
        payload = {
            "available": False,
            "note": "Train BLUE-0.1.2 and BLUE-0.2.0 before comparing.",
            "p1_exists": p1_path.exists(),
            "p2_exists": p2_path.exists(),
        }
        if persist:
            P2_COMPARE_PATH.parent.mkdir(parents=True, exist_ok=True)
            P2_COMPARE_PATH.write_text(json.dumps(payload, indent=2, default=str))
        return payload
    clf = BlueAttackClassifier.load(ARTIFACT_V020)
    if not clf.fitted:
        clf = BlueAttackClassifier.load(ARTIFACT_V012)
    p1 = score_model_coverage(payments, BlueTeam.load(p1_path), attacks, classifier=clf if clf.fitted else None)
    p2 = score_model_coverage(payments, BlueTeam.load(p2_path), attacks, classifier=clf if clf.fitted else None)
    frozen = score_model_coverage(payments, BlueTeam.load(FROZEN_BLUE), attacks, classifier=None)
    lanes = {
        "p1": _context_block(p1["families"]),
        "p2": _context_block(p2["families"]),
        "frozen": _context_block(frozen["families"]),
    }

    def _delta(metric: str) -> dict[str, float | None]:
        a = (p1.get("binary") or {}).get(metric)
        b = (p2.get("binary") or {}).get(metric)
        if a is None or b is None:
            return {"p1": a, "p2": b, "delta": None}
        return {"p1": float(a), "p2": float(b), "delta": float(b) - float(a)}

    payload = {
        "available": True,
        "seed": COVERAGE_SEED,
        "n_each": n_each,
        "n_attacks": int(len(attacks)),
        "frozen": frozen,
        "p1": p1,
        "p2": p2,
        "context": lanes,
        "improvement": {
            "recall": _delta("recall"),
            "precision": _delta("precision"),
            "f1": _delta("f1"),
            "pr_auc": _delta("pr_auc"),
            "fpr": _delta("fpr"),
            "mule_detection": {"p1": lanes["p1"]["mule"], "p2": lanes["p2"]["mule"], "delta": lanes["p2"]["mule"] - lanes["p1"]["mule"]},
            "beneficiary": {"p1": lanes["p1"]["beneficiary"], "p2": lanes["p2"]["beneficiary"], "delta": lanes["p2"]["beneficiary"] - lanes["p1"]["beneficiary"]},
            "shared_device": {"p1": lanes["p1"]["device"], "p2": lanes["p2"]["device"], "delta": lanes["p2"]["device"] - lanes["p1"]["device"]},
            "geo": {"p1": lanes["p1"]["geo"], "p2": lanes["p2"]["geo"], "delta": lanes["p2"]["geo"] - lanes["p1"]["geo"]},
            "network": {"p1": lanes["p1"]["network"], "p2": lanes["p2"]["network"], "delta": lanes["p2"]["network"] - lanes["p1"]["network"]},
        },
        "note": "Same seed and attack mix. Mix-set PR-AUC is not the headline. Numbers are measured, not targets.",
    }
    if persist:
        P2_COMPARE_PATH.parent.mkdir(parents=True, exist_ok=True)
        P2_COMPARE_PATH.write_text(json.dumps(payload, indent=2, default=str))
    return payload


def load_p1_vs_p2() -> dict[str, Any] | None:
    if P2_COMPARE_PATH.exists():
        return json.loads(P2_COMPARE_PATH.read_text())
    return None

