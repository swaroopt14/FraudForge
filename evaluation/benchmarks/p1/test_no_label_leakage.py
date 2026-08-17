from app.core.config import FEATURE_COLUMNS
from app.evaluation.leakage import leakage_paths
from app.fraud.pipeline import feature_matrix


def test_no_label_leakage(payments) -> None:
    assert leakage_paths() == []
    forbidden = {
        "attack_id",
        "attack_family",
        "attack_type",
        "simulation_id",
        "variant_id",
        "fraud_label",
        "agent_id",
        "intent_id",
        "red_team_score",
        "difficulty",
        "attack_success",
        "seed",
        "ground_truth",
    }
    assert forbidden.isdisjoint(FEATURE_COLUMNS)
    cols = set(feature_matrix(payments.head(10)).columns)
    assert forbidden.isdisjoint(cols)
