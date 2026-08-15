"""Local event log and failure artifacts. Synthetic only."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from config import DEMO_DIR

EVENTS_PATH = DEMO_DIR / "sim_events.jsonl"
FAILURES_PATH = DEMO_DIR / "sim_failures.jsonl"
HARD_NEG_PATH = DEMO_DIR / "sim_hard_negatives.jsonl"
REGISTRY_PATH = DEMO_DIR / "sim_model_registry.json"


def _append(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row) + "\n")


def append_event(event: dict[str, Any]) -> None:
    _append(EVENTS_PATH, event)


def append_failure(artifact: dict[str, Any]) -> None:
    _append(FAILURES_PATH, artifact)


def append_hard_negative(row: dict[str, Any]) -> None:
    _append(HARD_NEG_PATH, row)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    out = []
    for line in path.read_text().splitlines():
        if line.strip():
            out.append(json.loads(line))
    return out


def load_registry() -> dict[str, Any]:
    if not REGISTRY_PATH.exists():
        payload = {
            "current": "v1.4.2",
            "versions": [
                {
                    "version": "v1.4.2",
                    "label": "Amount-only (weak)",
                    "mode": "weak",
                    "training_examples": 0,
                    "note": "Baseline that ignores destination / intent.",
                }
            ],
        }
        REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
        REGISTRY_PATH.write_text(json.dumps(payload, indent=2))
        return payload
    return json.loads(REGISTRY_PATH.read_text())


def register_version(entry: dict[str, Any]) -> dict[str, Any]:
    payload = load_registry()
    versions = payload.get("versions") or []
    versions = [v for v in versions if v.get("version") != entry.get("version")]
    versions.append(entry)
    payload["versions"] = versions
    payload["current"] = entry.get("version")
    REGISTRY_PATH.write_text(json.dumps(payload, indent=2))
    return payload
