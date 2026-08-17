from app.core.config import FEATURE_COLUMNS
from app.core.model_registry import FROZEN_BLUE, FROZEN_BLUE_SHA256, load_registry, sha256_file
from app.evaluation.leakage import leakage_paths
from app.evaluation.metrics import red_scorecard
from app.blue_team.knowledge import export_defense_library, load_entry
from app.blue_team.classifiers.attack_classifier import BlueAttackClassifier, train_from_overlays
from app.blue_team.classifiers.fraud_detector import BlueFraudDetector
from app.blue_team.risk import combine
from app.red_team.compiler import compile_strategy
from app.red_team.models.attack_strategy import RedTeamAttackIntelligence
from app.red_team.models.novelty import RedTeamNoveltyModel
from app.red_team.validator import validate_strategy
from app.threats.registry import get_registry


def test_frozen_blue_untouched() -> None:
    assert FROZEN_BLUE.exists()
    assert sha256_file(FROZEN_BLUE) == FROZEN_BLUE_SHA256
    reg = load_registry()
    assert reg["blue_team"]["fraud_detector"]["status"] == "frozen"
    assert reg["red_team"]["attack_strategy"]["version"] == "RED-0.1.0"


def test_no_shared_prediction_model() -> None:
    rec = RedTeamAttackIntelligence().recommend(n=1)
    assert rec["not"] == "fraud_probability"
    assert rec["recommendation"]["attack_id"]
    assert "expected_attack_success" in rec["recommendation"]
    assert "fraud_probability" not in rec["recommendation"]


def test_leakage_still_empty() -> None:
    assert leakage_paths() == []
    assert "seed" not in FEATURE_COLUMNS
    assert "attack_id" not in FEATURE_COLUMNS
    assert "red_team_score" not in FEATURE_COLUMNS


def test_validator_and_compiler() -> None:
    ok = validate_strategy({"attack_id": "BEN-001", "difficulty": "medium"})
    assert ok["valid"] is True
    bad = validate_strategy({"attack_id": "NOT-A-THREAT"})
    assert bad["valid"] is False
    live = validate_strategy({"attack_id": "ATO-001", "note": "live_rail exploit"})
    assert live["valid"] is False
    contract = compile_strategy({"attack_id": "MUL-001", "difficulty": "high"}, seed=9, transaction_count=40)
    assert contract.attack_id == "MUL-001"


def test_novelty_is_not_an_llm_claim() -> None:
    threat = get_registry().get("ATO-001")
    scored = RedTeamNoveltyModel().score_threat(threat)
    assert scored["backend"] in {"hashing", "sentence-transformers"}
    assert scored["nearest_known_attack"] != "ATO-001"


def test_defense_library_and_risk() -> None:
    export_defense_library()
    mul = load_entry("MUL-001")
    assert mul["attack_id"] == "MUL-001"
    assert mul["identification"]["classifier_label"] == "mule_network"
    risk = combine(0.12)
    assert risk["network"]["enabled"] is False
    assert risk["network"]["value"] is None


def test_attack_classifier_unknown_without_fit() -> None:
    import pandas as pd

    clf = BlueAttackClassifier()
    frame = pd.DataFrame([{col: 0.0 for col in FEATURE_COLUMNS}])
    out = clf.predict(frame)
    assert out[0]["family"] in {"UNKNOWN", "EMERGING"}


def test_linked_red_blue_reports(controller) -> None:
    intel = RedTeamAttackIntelligence()
    intel.fit()
    intel.save()
    RedTeamNoveltyModel().save()
    result = controller.run(
        "BEN-001",
        difficulty="MEDIUM",
        transaction_count=40,
        seed=424242,
        persist=True,
        explain=False,
    )
    assert "RED TEAM ATTACK REPORT" in result["report"]
    assert result["blue_report"]["simulation_id"] == result["simulation_id"]
    assert result["red_feedback"]["simulation_id"] == result["simulation_id"]
    assert result["blue_feedback"]["simulation_id"] == result["simulation_id"]
    assert "time_to_detect_ms" in result["blue_report"]
    card = red_scorecard(result)
    assert "attack_success_rate" in card
    clf = train_from_overlays(controller.payments, controller.registry, n_each=16)
    clf.save()
    detector = BlueFraudDetector(controller.team)
    scores = detector.score(controller.generate(controller.build_contract("VEL-001", transaction_count=20, seed=1)))
    assert len(scores) == 20
