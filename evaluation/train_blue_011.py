#!/usr/bin/env python3
"""Train BLUE-0.1.1 without touching the frozen 0.1.0 artifact.

    python -m evaluation.train_blue_011
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))


def main() -> int:
    from app.blue_team.train import train_blue_011
    from app.data.ingest import load_payments

    payments = load_payments()
    result = train_blue_011(payments, n_each=80, persist=True)
    print(json.dumps({k: v for k, v in result.items() if k != "coverage"}, indent=2, default=str))
    if result.get("coverage"):
        print("wrote evaluation/benchmarks/p1/attack_coverage.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
