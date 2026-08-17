from __future__ import annotations

import numpy as np

from app.redteam.mutations import apply_mutation
from app.simulation.legit import generate_legitimate

PAIRS = [
    ("ATO-001", "ATO-V01", "ATO-V05"),
    ("VEL-001", "VEL-V01", "VEL-V05"),
    ("AMT-001", "AMT-V01", "AMT-V05"),
    ("GEO-001", "GEO-V01", "GEO-V05"),
    ("FRAG-001", "FRAG-V01", "FRAG-V05"),
]


def test_detection_metrics(controller) -> None:
    lows = []
    highs = []
    for attack_id, loud, quiet in PAIRS:
        low = controller.execute(
            controller.build_contract(attack_id, variant_id=loud, difficulty="LOW", transaction_count=120, seed=21),
            persist=False,
            explain=False,
        )
        high = controller.execute(
            controller.build_contract(attack_id, variant_id=quiet, difficulty="HIGH", transaction_count=120, seed=21),
            persist=False,
            explain=False,
        )
        for key in ("precision", "recall", "f1", "pr_auc", "fpr", "detection_rate"):
            assert 0.0 <= low["metrics"][key] <= 1.0
            assert 0.0 <= high["metrics"][key] <= 1.0
        lows.append(low["metrics"]["detection_rate"])
        highs.append(high["metrics"]["detection_rate"])
    assert sum(lows) / len(lows) >= sum(highs) / len(highs) - 1e-9


def test_difficulty_gradient(controller) -> None:
    """Aggregate Detection(LOW) >= Detection(MEDIUM) >= Detection(HIGH) on difficulty knobs only."""
    base = generate_legitimate(controller.profiles(), 150, seed=21)
    by_level = {"LOW": [], "MEDIUM": [], "HIGH": []}
    for attack_id, _, _ in PAIRS:
        threat = controller.registry.get(attack_id)
        for level in ("LOW", "MEDIUM", "HIGH"):
            rng = np.random.default_rng(21)
            rows = apply_mutation(base.copy(), threat.difficulty_levels[level], rng, threat.family)
            proba = controller.team.score(rows)
            by_level[level].append(float(np.mean(proba)))
    low = sum(by_level["LOW"]) / len(by_level["LOW"])
    mid = sum(by_level["MEDIUM"]) / len(by_level["MEDIUM"])
    high = sum(by_level["HIGH"]) / len(by_level["HIGH"])
    assert low + 1e-9 >= mid
    assert mid + 1e-9 >= high
