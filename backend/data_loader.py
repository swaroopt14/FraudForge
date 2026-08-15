"""Load and cache the processed credit-card table."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from config import CREDITCARD_PATH, FEATURE_COLUMNS, LABEL_COL, RANDOM_STATE
from features import feature_matrix, overlay_real_dataset


def synthesize_creditcard(n: int = 40_000, fraud_rate: float = 0.02, seed: int = RANDOM_STATE) -> pd.DataFrame:
    """Schema-compatible stand-in when the Kaggle/TF CSV cannot be downloaded."""
    rng = np.random.default_rng(seed)
    n_fraud = max(200, int(n * fraud_rate))
    n_legit = n - n_fraud
    rows = []
    for is_fraud, count in ((0, n_legit), (1, n_fraud)):
        block = {
            "Time": rng.uniform(0, 172800, count),
            "Amount": np.clip(rng.lognormal(3.2 if is_fraud else 2.6, 1.15, count), 0.01, 8000),
            "Class": np.full(count, is_fraud),
        }
        for i in range(1, 29):
            loc = 0.9 * is_fraud if i in {10, 12, 14, 17} else 0.0
            block[f"V{i}"] = rng.normal(loc, 1.0, count)
        rows.append(pd.DataFrame(block))
    df = pd.concat(rows, ignore_index=True)
    return df.sample(frac=1.0, random_state=seed).reset_index(drop=True)


def load_raw(path: Path | None = None) -> pd.DataFrame:
    csv_path = path or CREDITCARD_PATH
    if csv_path.exists() and csv_path.stat().st_size > 1_000_000:
        df = pd.read_csv(csv_path)
    else:
        print(f"CSV missing at {csv_path}; synthesizing a schema-compatible table")
        df = synthesize_creditcard()
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(csv_path, index=False)
    required = ["Time", "Amount", LABEL_COL] + [f"V{i}" for i in range(1, 29)]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Unexpected schema, missing: {missing}")
    return df


def load_processed(path: Path | None = None, seed: int = RANDOM_STATE) -> pd.DataFrame:
    df = load_raw(path)
    return overlay_real_dataset(df, seed=seed)


def xy(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    X = feature_matrix(df)
    y = df[LABEL_COL].astype(int)
    return X, y


def fraud_only(df: pd.DataFrame) -> pd.DataFrame:
    return df.loc[df[LABEL_COL] == 1].copy()


def legitimate_only(df: pd.DataFrame) -> pd.DataFrame:
    return df.loc[df[LABEL_COL] == 0].copy()


__all__ = ["FEATURE_COLUMNS", "fraud_only", "legitimate_only", "load_processed", "load_raw", "xy"]
