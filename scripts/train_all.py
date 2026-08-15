"""Train detector, CTGAN, autoencoder, and precompute demo artifacts."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))

from download_data import download  # noqa: E402

from agents.anomaly_detector import AnomalyDetector  # noqa: E402
from agents.attack_generator import AttackGenerator  # noqa: E402
from agents.fraud_detector import FraudDetector  # noqa: E402
from closed_loop import run_closed_loop  # noqa: E402
from config import (  # noqa: E402
    AE_EPOCHS,
    AE_SUBSAMPLE,
    CTGAN_EPOCHS,
    DEMO_DIR,
    SCENARIOS_PATH,
)
from data_loader import load_processed, load_raw, xy  # noqa: E402
from features import feature_matrix  # noqa: E402
from service import build_scenario_fixtures  # noqa: E402


def main() -> None:
    download()
    processed = load_processed()
    X, y = xy(processed)

    print("=== XGBoost detector ===")
    detector = FraudDetector()
    metrics = detector.train(X, y)
    detector.save()
    print(json.dumps(metrics, indent=2))
    if metrics["f1"] < 0.80:
        raise SystemExit(f"F1 {metrics['f1']:.3f} is below 0.80")

    print("=== CTGAN ===")
    raw = load_raw()
    fraud = raw.loc[raw["Class"] == 1].copy()
    generator = AttackGenerator(fraud_samples=fraud)
    try:
        generator.train(epochs=CTGAN_EPOCHS)
        generator.save()
        sample = generator.generate_synthetic_fraud(400, family=None)
        print(json.dumps(generator.evaluate_fidelity(sample, fraud), indent=2))
    except Exception as exc:  # noqa: BLE001
        print(f"CTGAN training skipped: {exc}")

    print("=== Autoencoder ===")
    legit = processed.loc[processed["Class"] == 0]
    ae = AnomalyDetector(input_dim=X.shape[1])
    ae.train(
        feature_matrix(legit).to_numpy(dtype=float),
        epochs=AE_EPOCHS,
        subsample=AE_SUBSAMPLE,
    )
    ae.save()
    print(f"Anomaly threshold={ae.threshold:.6f}")

    print("=== Closed loop ===")
    loop = run_closed_loop(detector=detector, generator=generator, persist=True)
    print(
        "attack_success",
        loop["attack_success_before"]["attack_success_rate"],
        "→",
        loop["attack_success_after"]["attack_success_rate"],
    )
    print("F1 mixed", loop["improvement"]["f1"])

    print("=== Scenarios ===")
    DEMO_DIR.mkdir(parents=True, exist_ok=True)
    scenarios = build_scenario_fixtures(processed)
    SCENARIOS_PATH.write_text(json.dumps(scenarios, indent=2))
    print(f"Wrote {SCENARIOS_PATH}")
    print("Done.")


if __name__ == "__main__":
    main()
