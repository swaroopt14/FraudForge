from __future__ import annotations

import numpy as np

from app.core.config import FEATURE_COLUMNS
from app.fraud.pipeline import BlueTeam, compute_metrics, feature_matrix, prepare_split, predict_proba
from app.risk.explain import explain_row
from app.risk.policy import decide
from app.simulation.attacks import generate_mixed_attacks


def test_no_label_leakage(payments) -> None:
    assert "attack_family" not in FEATURE_COLUMNS
    assert "fraud_label" not in FEATURE_COLUMNS
    X = feature_matrix(payments)
    assert list(X.columns) == FEATURE_COLUMNS


def test_models_and_proba(payments) -> None:
    attacks = generate_mixed_attacks(payments, n_each=80)
    train, test = prepare_split(payments, attacks, seed=1)
    team = BlueTeam()
    metrics = team.train(train, test)
    X = feature_matrix(test.head(20))
    pa = predict_proba(team.logreg, X)
    pb = predict_proba(team.lgbm, X)
    assert pa.min() >= 0 and pa.max() <= 1
    assert pb.min() >= 0 and pb.max() <= 1
    assert metrics["lightgbm"]["pr_auc"] >= metrics["logreg"]["pr_auc"] - 1e-9
    y = test["fraud_label"].to_numpy()
    again = compute_metrics(y, team.score(test))
    assert again["recall"] == metrics["lightgbm"]["recall"]
    pairs = team.importance_pairs(X, test["fraud_label"].astype(int).head(20))
    assert len(pairs) == len(FEATURE_COLUMNS)
    assert sum(value for _, value in pairs) > 0
    assert metrics["feature_importance"][0]["importance"] > 0


def test_policy_thresholds() -> None:
    assert decide(0.10) == "ALLOW"
    assert decide(0.45) == "STEP_UP"
    assert decide(0.70) == "REVIEW"
    assert decide(0.90) == "BLOCK"
    assert decide(0.50, allow=0.1, step_up=0.2, review=0.4) == "BLOCK"


def test_shap_finite(payments) -> None:
    attacks = generate_mixed_attacks(payments, n_each=40)
    train, test = prepare_split(payments, attacks, seed=2)
    team = BlueTeam()
    team.train(train, test)
    exp = explain_row(team.lgbm, test.head(1))
    assert len(exp) >= 1
    assert all(np.isfinite(e["shap_value"]) for e in exp)
    assert all(e["feature"] in FEATURE_COLUMNS for e in exp)
