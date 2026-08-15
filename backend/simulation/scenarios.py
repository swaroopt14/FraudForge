"""JSON-backed scenario catalog."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from config import DEMO_DIR

SCENARIOS_PATH = DEMO_DIR / "sim_scenarios.json"


def load_all_scenarios(path: Path | None = None) -> list[dict[str, Any]]:
    payload = json.loads((path or SCENARIOS_PATH).read_text())
    return list(payload.get("scenarios") or [])


def list_scenarios() -> list[dict[str, Any]]:
    return [
        {
            "scenario_id": s["scenario_id"],
            "name": s["name"],
            "severity": s.get("severity"),
            "attack_family": s.get("attack_family"),
            "expected_outcome": s.get("expected_outcome"),
            "description": s.get("description"),
        }
        for s in load_all_scenarios()
    ]


def load_scenario(scenario_id: str) -> dict[str, Any]:
    for row in load_all_scenarios():
        if row.get("scenario_id") == scenario_id:
            return row
    raise KeyError(f"Unknown scenario: {scenario_id}")
