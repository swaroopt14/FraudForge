"""Red Team memory: attack histories and Blue-Team reports. Not Blue training rows."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from app.core.config import RED_MEMORY_DIR, ensure_dirs

MEMORY_PATH = RED_MEMORY_DIR / "attacks.jsonl"


def record(event: dict[str, Any]) -> None:
    ensure_dirs()
    payload = {
        **event,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "owner": "red_team",
    }
    with MEMORY_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, default=str) + "\n")


def recent(limit: int = 20) -> list[dict[str, Any]]:
    if not MEMORY_PATH.exists():
        return []
    lines = MEMORY_PATH.read_text(encoding="utf-8").splitlines()
    out = []
    for line in lines[-limit:]:
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return list(reversed(out))
