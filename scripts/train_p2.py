#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.blue_team.service import train_p2  # noqa: E402

if __name__ == "__main__":
    team = train_p2()
    print(json.dumps({"model_id": team.metrics.get("model_id"), "metrics": team.metrics}, indent=2, default=str))
