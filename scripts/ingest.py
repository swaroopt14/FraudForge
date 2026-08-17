#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.data.ingest import ingest  # noqa: E402

if __name__ == "__main__":
    df = ingest()
    print(f"payments={len(df)} fraud_rate={df['fraud_label'].mean():.4f}")
