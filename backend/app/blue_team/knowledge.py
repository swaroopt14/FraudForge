"""Defense knowledge base compiled from the Threat Library. No invented detections."""

from __future__ import annotations

import json
from typing import Any

from app.core.config import BLUE_DEFENSE_DIR, ensure_dirs
from app.threats.registry import get_registry

SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "BlueDefenseEntry",
    "type": "object",
    "required": ["attack_id", "detection", "identification", "mitigation"],
    "properties": {
        "attack_id": {"type": "string"},
        "detection": {"type": "object"},
        "identification": {"type": "object"},
        "mitigation": {"type": "object"},
    },
}


def entry_from_threat(threat) -> dict[str, Any]:
    return {
        "attack_id": threat.attack_id,
        "name": threat.name,
        "observable_signals": list(threat.detection_signals),
        "detection": {
            "signals": list(threat.detection_signals),
            "features": list(threat.required_features),
            "phase_note": "P1 uses tabular FEATURE_COLUMNS only. Network/geo/intent/agent signals are listed, not scored.",
        },
        "identification": {"classifier_label": threat.family},
        "investigation_signals": list(threat.detection_signals),
        "mitigation": {
            "medium": "REVIEW",
            "high": "STEP_UP",
            "critical": "BLOCK",
            "expected": threat.expected_mitigation,
        },
        "false_positive_cases": [
            "IEEE legit already contains new-beneficiary rows; do not treat beneficiary_is_new alone as fraud."
        ],
        "recommended_tests": [f"replay {threat.attack_id} MEDIUM seed=424242 n=1000"],
    }


def export_defense_library() -> list[str]:
    ensure_dirs()
    (BLUE_DEFENSE_DIR / "schemas" / "defense.schema.json").write_text(json.dumps(SCHEMA, indent=2))
    written = []
    for threat in get_registry().list():
        body = entry_from_threat(threat)
        for folder in ("detection", "identification", "mitigation"):
            path = BLUE_DEFENSE_DIR / folder / f"{threat.attack_id}.json"
            path.write_text(json.dumps(body, indent=2))
            written.append(str(path))
    playbook = {
        "id": "P1-REVIEW-BLOCK",
        "actions": ["ALLOW", "STEP_UP", "REVIEW", "BLOCK"],
        "rule": "decide(fraud_probability) with ALLOW 0.30 / STEP_UP 0.60 / REVIEW 0.80",
        "note": "Policy is deterministic. ML does not pick the action.",
    }
    (BLUE_DEFENSE_DIR / "playbooks" / "p1_policy.json").write_text(json.dumps(playbook, indent=2))
    return written


def load_entry(attack_id: str) -> dict[str, Any]:
    path = BLUE_DEFENSE_DIR / "detection" / f"{attack_id}.json"
    if path.exists():
        return json.loads(path.read_text())
    threat = get_registry().get(attack_id)
    return entry_from_threat(threat)
