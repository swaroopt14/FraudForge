#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.service import train_models  # noqa: E402

if __name__ == "__main__":
    team = train_models()
    print(json.dumps(team.metrics, indent=2, default=str))
