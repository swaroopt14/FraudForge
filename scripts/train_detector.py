"""Train the XGBoost detector and persist detector.pkl."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))

from download_data import download  # noqa: E402

from agents.fraud_detector import FraudDetector  # noqa: E402
from data_loader import load_processed, xy  # noqa: E402


def main() -> None:
    download()
    df = load_processed()
    X, y = xy(df)
    detector = FraudDetector()
    metrics = detector.train(X, y)
    path = detector.save()
    print(json.dumps(metrics, indent=2))
    print(f"Saved {path}")
    if metrics["f1"] < 0.80:
        raise SystemExit(f"F1 {metrics['f1']:.3f} is below 0.80")


if __name__ == "__main__":
    main()
