"""P1/P2 adapter: observable context features without label leakage."""

from __future__ import annotations

from typing import Any

import pandas as pd

from app.blue_team.features import attach_p2_features
from app.blue_team.graph import cluster_stats
from app.core.config import FEATURE_COLUMNS_V020

P2_COLUMNS = FEATURE_COLUMNS_V020


def ensure_p2(df: pd.DataFrame) -> pd.DataFrame:
    return attach_p2_features(df)


def network_summary(df: pd.DataFrame) -> dict[str, Any]:
    stats = cluster_stats(df)
    return {
        **stats,
        "rows": int(len(df)),
        "phase": "P2",
    }
