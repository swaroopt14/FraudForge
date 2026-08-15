"""Prepare a deployable runtime: data + detector if they are missing.

Does not train CTGAN or the autoencoder. Identify / Generate / Defend
and /detect work after this step. Full local training is scripts/train_all.py.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))

from download_data import download  # noqa: E402

from agents.fraud_detector import FraudDetector  # noqa: E402
from config import DEMO_DIR, DETECTOR_PATH, SCENARIOS_PATH  # noqa: E402
from data_loader import load_processed, xy  # noqa: E402
from service import build_scenario_fixtures  # noqa: E402


def main() -> None:
    download()
    if DETECTOR_PATH.exists():
        print(f"Detector already present: {DETECTOR_PATH}")
    else:
        print("Training detector (first boot)…")
        df = load_processed()
        X, y = xy(df)
        detector = FraudDetector()
        metrics = detector.train(X, y)
        detector.save()
        print(json.dumps(metrics, indent=2))
        print(f"Saved {DETECTOR_PATH}")

    DEMO_DIR.mkdir(parents=True, exist_ok=True)
    if not SCENARIOS_PATH.exists():
        scenarios = build_scenario_fixtures(load_processed())
        SCENARIOS_PATH.write_text(json.dumps(scenarios, indent=2))
        print(f"Wrote {SCENARIOS_PATH}")
    print("Bootstrap ready.")


if __name__ == "__main__":
    main()
