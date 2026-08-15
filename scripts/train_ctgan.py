"""Fit CTGAN on real fraud rows."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))

from download_data import download  # noqa: E402

from agents.attack_generator import AttackGenerator  # noqa: E402
from config import CTGAN_EPOCHS  # noqa: E402
from data_loader import load_raw  # noqa: E402


def main() -> None:
    download()
    raw = load_raw()
    fraud = raw.loc[raw["Class"] == 1].copy()
    print(f"Fitting CTGAN on {len(fraud)} fraud rows, epochs={CTGAN_EPOCHS}")
    gen = AttackGenerator(fraud_samples=fraud)
    gen.train(epochs=CTGAN_EPOCHS)
    path = gen.save()
    sample = gen.generate_synthetic_fraud(n_samples=min(500, len(fraud)), family=None)
    fidelity = gen.evaluate_fidelity(sample, fraud)
    print(json.dumps(fidelity, indent=2))
    print(f"Saved {path}")


if __name__ == "__main__":
    main()
