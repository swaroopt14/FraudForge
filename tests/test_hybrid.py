"""Hybrid defender: rules score only; intent can BLOCK; weak rules cannot."""

from __future__ import annotations

import pandas as pd

from agents.hybrid_scorer import intent_score, rules_score, score_hybrid


def _row(**kwargs) -> pd.DataFrame:
    base = {
        "Amount": 400.0,
        "Time": 1000.0,
        "device_new": 0,
        "velocity_1h": 1,
        "location_mismatch": 0,
        "beneficiary_name_match": 1,
        "mule_account_risk": 0.05,
        "constraint_violation": 0,
        "amount_vs_limit_ratio": 0.2,
        "hour_of_day": 12.0,
    }
    base.update(kwargs)
    return pd.DataFrame([base])


def test_rules_do_not_block_alone() -> None:
    df = _row(velocity_1h=9, device_new=1, location_mismatch=1)
    out = score_hybrid(df, ml_proba=[0.1], graph_scores=[0.1], threshold=0.9)
    assert out["block"][0] == 0
    assert out["decision"][0] == "APPROVE"
    assert out["rules"][0] > 0.2


def test_intent_constraint_blocks() -> None:
    df = _row(constraint_violation=1, amount_vs_limit_ratio=0.4)
    out = score_hybrid(df, ml_proba=[0.1], graph_scores=[0.0], threshold=0.9)
    assert out["intent"][0] == 1.0
    assert out["intent_block"][0] == 1
    assert out["block"][0] == 1
    assert out["decision"][0] == "BLOCK"


def test_amount_over_limit_blocks() -> None:
    df = _row(constraint_violation=0, amount_vs_limit_ratio=1.4)
    assert float(intent_score(df)[0]) == 1.0
    out = score_hybrid(df, ml_proba=[0.05], graph_scores=[0.0], threshold=0.9)
    assert out["decision"][0] == "BLOCK"


def test_tree_block_without_intent() -> None:
    df = _row()
    out = score_hybrid(df, ml_proba=[0.95], graph_scores=[0.0], threshold=0.5)
    assert out["tree_block"][0] == 1
    assert out["intent_block"][0] == 0
    assert out["decision"][0] == "BLOCK"


def test_legit_row_low_rules() -> None:
    df = _row()
    assert float(rules_score(df)[0]) < 0.2
    assert float(intent_score(df)[0]) == 0.0


def test_kyc_rules_do_not_block_alone() -> None:
    df = _row(
        kyc_liveness_risk=0.95,
        document_tamper_score=0.92,
        biometric_mismatch=1,
        voiceprint_mismatch=1,
    )
    out = score_hybrid(df, ml_proba=[0.1], graph_scores=[0.1], threshold=0.9)
    assert out["decision"][0] == "APPROVE"
    assert out["rules"][0] > 0.2
