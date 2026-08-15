"""Closed-loop evaluation: novel attacks, hold-out scoring, detector retrain."""

from __future__ import annotations

import json
from typing import Any

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split

from agents.adversarial_optimizer import AdversarialOptimizer
from agents.attack_generator import AttackGenerator
from agents.evaluation_agent import EvaluationAgent
from agents.feedback_agent import FeedbackAgent
from agents.fraud_detector import FraudDetector
from attack_catalog import FAMILY_LABELS
from config import (
    ATTACK_FAMILIES,
    CLOSED_LOOP_PATH,
    DEMO_DIR,
    FEATURE_COLUMNS,
    HOLDOUT_FAMILY,
    RANDOM_STATE,
)
from data_loader import load_processed, xy
from features import feature_matrix, overlay_family


def _novel_holdout_attacks(processed: pd.DataFrame, n: int, rng: np.random.Generator) -> pd.DataFrame:
    """Fraud-like amounts on a legitimate PCA signature with washed narrative flags.

    The initial detector leans on overlay features; these rows look like high-value
    genuine spend until the loop retrains on them.
    """
    from features import overlay_legitimate

    legit = processed.loc[processed["Class"] == 0]
    idx = rng.choice(len(legit), size=n, replace=False)
    seed = legit.iloc[idx].copy().reset_index(drop=True)
    attacks = overlay_legitimate(seed, rng)
    attacks["Amount"] = rng.uniform(900.0, 3800.0, size=n)
    attacks["amount_vs_limit_ratio"] = rng.uniform(0.55, 1.35, size=n)
    attacks["Class"] = 1
    attacks["attack_family"] = HOLDOUT_FAMILY
    attacks["attack_source"] = "novel_holdout"
    return attacks


def _ctgan_family_attacks(generator: AttackGenerator, n: int, rng: np.random.Generator) -> pd.DataFrame:
    attacks = generator.generate_synthetic_fraud(n, family=HOLDOUT_FAMILY, rng=rng)
    attacks["attack_source"] = "ctgan_holdout"
    return attacks


def run_closed_loop(
    detector: FraudDetector | None = None,
    generator: AttackGenerator | None = None,
    persist: bool = True,
    n_novel: int = 220,
    n_synth: int = 180,
) -> dict[str, Any]:
    rng = np.random.default_rng(RANDOM_STATE)
    processed = load_processed()
    X, y = xy(processed)
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=RANDOM_STATE, stratify=y
    )

    if detector is None:
        detector = FraudDetector()
        detector.train(X, y)

    if generator is None:
        fraud = processed.loc[processed["Class"] == 1]
        generator = AttackGenerator(fraud_samples=fraud)
        # Prefer already-fitted synthesizer if present.
        from config import CTGAN_PATH

        if CTGAN_PATH.exists() and CTGAN_PATH.stat().st_size > 20:
            generator = AttackGenerator.load(fraud_samples=fraud)

    novel = _novel_holdout_attacks(processed, n_novel, rng)
    try:
        synth = _ctgan_family_attacks(generator, n_synth, rng)
    except Exception:  # noqa: BLE001
        synth = _novel_holdout_attacks(processed, n_synth, rng)
        synth["attack_source"] = "bootstrap_holdout"

    pool = pd.concat([novel, synth], ignore_index=True)
    optimizer = AdversarialOptimizer(detector)
    pool = optimizer.generate_adversarial_attacks(pool)

    train_att, hold_att = train_test_split(
        pool, test_size=0.28, random_state=RANDOM_STATE
    )

    evaluator = EvaluationAgent(detector)
    before = evaluator.evaluate_attack_success(hold_att)
    metrics_before = dict(detector.metrics)

    mixed_before_X = pd.concat([X_test, feature_matrix(hold_att)], ignore_index=True)
    mixed_before_y = pd.concat(
        [y_test.reset_index(drop=True), pd.Series(np.ones(len(hold_att), dtype=int))],
        ignore_index=True,
    )
    mixed_metrics_before = evaluator.classification_metrics(mixed_before_X, mixed_before_y)

    X_aug = pd.concat([X_train, feature_matrix(train_att)], ignore_index=True)
    y_aug = pd.concat(
        [y_train.reset_index(drop=True), pd.Series(np.ones(len(train_att), dtype=int))],
        ignore_index=True,
    )
    retrained = FraudDetector()
    after_metrics_holdout = retrained.train(X_aug, y_aug)

    eval_after = EvaluationAgent(retrained)
    after = eval_after.evaluate_attack_success(hold_att, threshold=retrained.threshold)

    mixed_after_X = pd.concat([X_test, feature_matrix(hold_att)], ignore_index=True)
    mixed_after_y = mixed_before_y
    mixed_metrics_after = eval_after.classification_metrics(mixed_after_X, mixed_after_y)

    original_after = eval_after.classification_metrics(X_test, y_test)
    fpr = eval_after.evaluate_false_positive_rate(X_test[y_test.to_numpy() == 0])

    scores_after = retrained.predict(hold_att)
    bypassed_mask = scores_after < retrained.threshold
    bypassed = hold_att.loc[bypassed_mask]
    detected = hold_att.loc[~bypassed_mask]
    feedback = FeedbackAgent()
    analysis = feedback.analyze_failures(bypassed, detected)
    new_hypotheses = feedback.generate_new_hypotheses(
        analysis, attack_history=list(FAMILY_LABELS.values())
    )

    improvement = evaluator.evaluate_detection_improvement(mixed_metrics_before, mixed_metrics_after)

    result = {
        "holdout_family": HOLDOUT_FAMILY,
        "n_train_attacks": int(len(train_att)),
        "n_holdout_attacks": int(len(hold_att)),
        "attack_success_before": before,
        "attack_success_after": after,
        "metrics_before": metrics_before,
        "metrics_after_retrained_split": after_metrics_holdout,
        "mixed_test_before": mixed_metrics_before,
        "mixed_test_after": mixed_metrics_after,
        "original_test_after": original_after,
        "fpr_after": fpr,
        "improvement": improvement,
        "failure_analysis": analysis,
        "new_hypotheses": new_hypotheses,
        "families": ATTACK_FAMILIES,
        "feature_columns": FEATURE_COLUMNS,
        "optimizer": "evolutionary_perturbation",
    }

    if persist:
        DEMO_DIR.mkdir(parents=True, exist_ok=True)
        CLOSED_LOOP_PATH.write_text(json.dumps(result, indent=2))
        retrained.save()  # keep the original detector for the live demo
        # Re-save the *original* detector — closed-loop should not overwrite demo weights.
        detector.save()

    return result


__all__ = ["run_closed_loop"]
