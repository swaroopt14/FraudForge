#!/usr/bin/env python3
"""RUN RED TEAM TEST: generate → score → metrics → missed → report."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.service import run_simulation, team  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--attack", default="low_and_slow")
    parser.add_argument("--n", type=int, default=10000)
    parser.add_argument("--seed", type=int, default=424242)
    parser.add_argument("--intensity", default="medium")
    args = parser.parse_args()
    team()  # ensure trained
    result = run_simulation(args.attack, args.n, args.seed, args.intensity)
    print(result["report"])
    print(f"simulation_id={result['simulation_id']} missed={result['missed']}")


if __name__ == "__main__":
    main()
