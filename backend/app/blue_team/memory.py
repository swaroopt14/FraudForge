"""Blue Team memory: hard negatives and missed rows. Metadata only until a new model version is trained."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from app.core.config import BLUE_MEMORY_DIR, FEATURE_COLUMNS, ensure_dirs

MEMORY_PATH = BLUE_MEMORY_DIR / "hard_negatives.jsonl"


def record_misses(simulation_id: str, rows: list[dict[str, Any]], model_version: str) -> None:
    ensure_dirs()
    for row in rows[:50]:
        observable = {k: row.get(k) for k in FEATURE_COLUMNS if k in row}
        payload = {
            "simulation_id": simulation_id,
            "transaction_id": row.get("transaction_id"),
            "fraud_probability": row.get("fraud_probability"),
            "decision": row.get("decision"),
            "observable": observable,
            "label": 1,
            "model_version": model_version,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "owner": "blue_team",
            "note": "Hard negative candidate. Do not train BLUE-0.1.0 in place; open BLUE-0.1.1+.",
        }
        with MEMORY_PATH.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, default=str) + "\n")
