#!/usr/bin/env python3
"""python -m evaluation.run_phase_benchmark p1"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

CHECKS = [
    ("Threat Definitions", "test_threat_schema.py"),
    ("Threat Coverage", "test_threat_registry.py"),
    ("Reproducibility", "test_attack_reproducibility.py"),
    ("Attack Variants", "test_attack_variants.py"),
    ("Scaling", "test_attack_scaling.py"),
    ("Fidelity", "test_attack_fidelity.py"),
    ("Detection Evaluation", "test_detection_metrics.py"),
    ("Leakage Check", "test_no_label_leakage.py"),
    ("API", "test_red_team_api.py"),
    ("Graph / Agents / Adaptive", "test_graph_agents.py"),
    ("Separate Red/Blue ML", "test_separate_systems.py"),
    ("P1 Hardening", "test_p1_hardening.py"),
    ("End-to-End", "test_end_to_end.py"),
]


def main() -> int:
    phase = (sys.argv[1] if len(sys.argv) > 1 else "p1").lower()
    if phase != "p1":
        print(f"Unknown phase: {phase}")
        return 2
    import pytest

    folder = ROOT / "evaluation" / "benchmarks" / "p1"
    results: list[tuple[str, bool]] = []
    failed = False
    for label, filename in CHECKS:
        rc = pytest.main(["-q", str(folder / filename)])
        ok = rc == 0
        results.append((label, ok))
        failed = failed or (not ok)
    lines = [
        "============================================",
        "P1 BENCHMARK",
        "============================================",
        "",
        "",
    ]
    width = max(len(label) for label, _ in results)
    for label, ok in results:
        lines.append(f"{label.ljust(width)}  {'PASS' if ok else 'FAIL'}")
    lines += [
        "",
        "",
        f"P1 STATUS: {'PASS' if not failed else 'FAIL'}",
        "============================================",
        "",
    ]
    text = "\n".join(lines)
    print(text)
    out = folder / "last_run.txt"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
