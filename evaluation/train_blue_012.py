#!/usr/bin/env python3
"""Train BLUE-0.1.2 (corpus-grounded beneficiary features). Does not touch BLUE-0.1.0.

    python -m evaluation.train_blue_012
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))


def main() -> int:
    from app.blue_team.train import train_blue_012
    from app.data.ingest import load_payments

    payments = load_payments()
    result = train_blue_012(payments, persist=True)
    print(json.dumps({k: v for k, v in result.items() if k != "coverage"}, indent=2, default=str))
    if result.get("coverage"):
        print("wrote evaluation/benchmarks/p1/attack_coverage.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
