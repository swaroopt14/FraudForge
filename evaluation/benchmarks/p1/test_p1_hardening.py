from app.blue_team.risk import combine, combine_calibrated, decide_v011
from app.core.config import FEATURE_COLUMNS, FEATURE_COLUMNS_V011, FEATURE_COLUMNS_V012, FEATURE_COLUMNS_V020
from app.core.model_registry import FROZEN_BLUE, FROZEN_BLUE_SHA256, sha256_file
from app.evaluation.leakage import leakage_paths
from app.fraud.pipeline import feature_matrix, prepare_split, prepare_split_balanced
from app.threats.taxonomy import taxonomy_payload


def test_frozen_feature_set_unchanged() -> None:
    assert len(FEATURE_COLUMNS) == 15
    assert leakage_paths() == []
    assert leakage_paths(list(FEATURE_COLUMNS_V011)) == []
    assert leakage_paths(list(FEATURE_COLUMNS_V012)) == []
    assert leakage_paths(list(FEATURE_COLUMNS_V020)) == []
    assert "network_risk" in FEATURE_COLUMNS_V020
    assert "beneficiary_fan_in" in FEATURE_COLUMNS_V020
    assert "network_risk" not in FEATURE_COLUMNS
    assert len(FEATURE_COLUMNS_V020) == len(FEATURE_COLUMNS) + 27
    assert "beneficiary_sender_count" in FEATURE_COLUMNS_V012
    assert "payee_novelty" in FEATURE_COLUMNS_V012
    assert "payee_novelty" not in FEATURE_COLUMNS
    assert "beneficiary_sender_count" not in FEATURE_COLUMNS
    assert "log_amount" in FEATURE_COLUMNS_V011
    assert "txn_count_1m" in FEATURE_COLUMNS_V011
    assert "log_amount" not in FEATURE_COLUMNS


def test_v011_features_do_not_rewrite_frozen_columns(payments) -> None:
    frozen = feature_matrix(payments.head(40))
    v011 = feature_matrix(payments.head(40), list(FEATURE_COLUMNS_V011))
    assert list(frozen.columns) == list(FEATURE_COLUMNS)
    assert list(v011.columns) == list(FEATURE_COLUMNS_V011)
    for col in FEATURE_COLUMNS:
        assert (frozen[col].to_numpy() == v011[col].to_numpy()).all()


def test_balanced_split_keeps_families(payments) -> None:
    from app.evaluation.coverage import generate_fixed_family_attacks

    attacks = generate_fixed_family_attacks(payments.head(4000), n_each=20, seed=7)
    _, old_test = prepare_split(payments.head(4000), attacks, seed=3)
    train, test = prepare_split_balanced(payments.head(4000), attacks, seed=3)
    old_families = set(old_test.loc[old_test["fraud_label"] == 1, "attack_family"].dropna())
    train_f = set(train.loc[train["fraud_label"] == 1, "attack_family"].dropna())
    test_f = set(test.loc[test["fraud_label"] == 1, "attack_family"].dropna())
    assert train_f == test_f
    assert len(train_f) >= 10
    # The P0 half-cut can drop families from train; balanced must not.
    assert old_families <= train_f | test_f


def test_taxonomy_and_v011_policy() -> None:
    tax = taxonomy_payload()
    assert tax["n_families"] >= 10
    assert tax["n_variants"] >= 30
    assert tax["chain"][0] == "threat"
    ato = next(f for f in tax["families"] if f["attack_id"] == "ATO-001")
    assert any(v["id"] == "ATO-V06" for v in ato["variants"])
    assert ato["observable_signals"]
    assert combine(0.12)["decision"] == "ALLOW"
    assert decide_v011(45) == "MONITOR"
    assert combine_calibrated(0.45)["decision"] == "MONITOR"
    assert combine_calibrated(0.45)["network"]["enabled"] is False
    from app.blue_team.risk import combine_p2

    p2 = combine_p2(0.45, network_risk=0.8, geo_risk=0.2)
    assert p2["network"]["enabled"] is True
    assert p2["geo"]["enabled"] is True
    assert p2["intent"]["enabled"] is False


def test_blue_011_does_not_touch_frozen(payments) -> None:
    from app.blue_team.classifiers.calibration import ProbabilityCalibrator
    from app.fraud.pipeline import BlueTeam
    from app.simulation.attacks import generate_mixed_attacks

    before = sha256_file(FROZEN_BLUE)
    assert before == FROZEN_BLUE_SHA256
    attacks = generate_mixed_attacks(payments.head(3000), n_each=30)
    train, test = prepare_split_balanced(payments.head(3000), attacks, seed=2)
    team = BlueTeam(feature_names=list(FEATURE_COLUMNS_V011), model_id="BLUE-0.1.1")
    team.train(train, test, calibrate=True)
    assert team.model_id == "BLUE-0.1.1"
    assert len(team.feature_names) == len(FEATURE_COLUMNS_V011)
    cal = ProbabilityCalibrator().fit(test["fraud_label"].to_numpy()[:80], team.score(test.head(80)))
    assert cal.fitted is True or len(set(test["fraud_label"].head(80))) < 2
    assert sha256_file(FROZEN_BLUE) == FROZEN_BLUE_SHA256


def test_corpus_grounds_beneficiary_signal(payments) -> None:
    import numpy as np

    from app.data.history import CorpusHistory
    from app.redteam.difficulty import resolve_mutation
    from app.redteam.mutations import apply_mutation
    from app.simulation.legit import fit_profiles, generate_legitimate
    from app.threats.registry import get_registry

    history = CorpusHistory.from_payments(payments)
    profiles = fit_profiles(payments)
    legit = generate_legitimate(profiles, 80, seed=9, history=history)
    assert float(legit["beneficiary_is_new"].mean()) < 0.35
    mutation = resolve_mutation(get_registry(), "BEN-001", "MEDIUM", "BEN-V01")
    atk = history.attach(
        apply_mutation(legit.copy(), mutation, np.random.default_rng(9), "beneficiary_anomaly"),
        refresh_concentration=False,
    )
    assert float(atk["beneficiary_is_new"].mean()) > 0.7
    assert "beneficiary_sender_count" in atk.columns
    assert float(atk.loc[atk["beneficiary_is_new"] > 0, "hours_since_pair"].median()) >= 24.0 * 30.0
    assert float(atk["payee_novelty"].mean()) > float(legit["payee_novelty"].mean())
    assert float(atk["beneficiary_sender_count"].mean()) <= float(legit["beneficiary_sender_count"].mean()) + 1.0
