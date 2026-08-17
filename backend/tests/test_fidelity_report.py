from __future__ import annotations

from app.evaluation.fidelity import fidelity_report
from app.evaluation.report import render_report
from app.simulation.legit import fit_profiles, generate_legitimate


def test_fidelity_computed(payments) -> None:
    legit = payments.loc[payments["fraud_label"] == 0]
    synth = generate_legitimate(fit_profiles(payments), 300, seed=4)
    report = fidelity_report(legit.head(800), synth)
    for key in ("amount_distribution", "time_distribution", "velocity_distribution", "merchant_distribution", "overall_fidelity"):
        assert 0.0 <= report[key] <= 1.0
    w = report["weights"]
    expected = (
        w["amount"] * report["amount_distribution"]
        + w["time"] * report["time_distribution"]
        + w["velocity"] * report["velocity_distribution"]
        + w["merchant"] * report["merchant_distribution"]
    )
    assert abs(expected - report["overall_fidelity"]) < 1e-6


def test_report_shape() -> None:
    text = render_report(
        "001",
        "low_and_slow",
        10000,
        {"precision": 0.918, "recall": 0.724, "f1": 0.809, "pr_auc": 0.88, "fpr": 0.017},
    )
    assert "ADVERSARIAL PAYMENT DEFENSE — RUN #001" in text
    assert "LOW_AND_SLOW" in text
    assert "10000" in text
    assert "Blue Team recommendation" in text
