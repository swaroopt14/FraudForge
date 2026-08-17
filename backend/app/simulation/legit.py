"""Sample realistic legitimate payments from IEEE-fitted customer profiles."""

from __future__ import annotations

import pandas as pd
import numpy as np

from app.core.config import RANDOM_STATE
from app.data.ingest import add_behavior_features


def fit_profiles(payments: pd.DataFrame) -> pd.DataFrame:
    legit = payments.loc[payments["fraud_label"] == 0].copy()
    if legit.empty:
        legit = payments.copy()
    rows = []
    for cid, part in legit.groupby("customer_id"):
        if len(part) < 2:
            continue
        rows.append(
            {
                "customer_id": cid,
                "amount_lo": float(part["amount"].quantile(0.15)),
                "amount_hi": float(part["amount"].quantile(0.85)),
                "amount_mean": float(part["amount"].mean()),
                "hour_mean": float(part["hour_of_day"].mean()),
                "hour_std": float(max(part["hour_of_day"].std(), 1.0)),
                "velocity": float(part["transaction_count_24h"].median()),
                "merchant_category": part["merchant_category"].mode().iloc[0],
                "payment_method": part["payment_method"].mode().iloc[0],
                "country": float(part["country"].median()),
                "device_id": part["device_id"].mode().iloc[0],
                "ip_id": part["ip_id"].mode().iloc[0],
                "merchant_id": part["merchant_id"].mode().iloc[0],
                "beneficiary_id": part["beneficiary_id"].mode().iloc[0],
                "account_age_days": float(part["account_age_days"].median()),
                "distance_from_home": float(part["distance_from_home"].median()),
            }
        )
    if not rows:
        raise ValueError("Not enough legitimate customers to fit profiles")
    return pd.DataFrame(rows)


def generate_legitimate(
    profiles: pd.DataFrame,
    n: int,
    seed: int = RANDOM_STATE,
    start_ts: float = 1_000_000.0,
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(profiles), size=n)
    chosen = profiles.iloc[idx].reset_index(drop=True)
    amounts = rng.uniform(chosen["amount_lo"].to_numpy(), np.maximum(chosen["amount_hi"].to_numpy(), chosen["amount_lo"] + 1))
    hours = np.clip(rng.normal(chosen["hour_mean"].to_numpy(), chosen["hour_std"].to_numpy()), 0.0, 23.99)
    spacing = np.clip(86400.0 / np.maximum(chosen["velocity"].to_numpy(), 1.0), 600.0, 86400.0)
    timestamps = start_ts + np.arange(n) * 0.0
    # per-customer local clock
    clocks: dict[str, float] = {}
    ts = []
    for i, cid in enumerate(chosen["customer_id"]):
        clocks[cid] = clocks.get(cid, start_ts + float(rng.uniform(0, 3600))) + float(spacing[i]) * float(rng.uniform(0.6, 1.4))
        ts.append(clocks[cid])
    out = pd.DataFrame(
        {
            "transaction_id": [f"syn-{seed}-{i}" for i in range(n)],
            "timestamp": ts,
            "amount": np.clip(amounts, 0.01, None),
            "merchant_category": chosen["merchant_category"],
            "payment_method": chosen["payment_method"],
            "country": chosen["country"],
            "distance_from_home": chosen["distance_from_home"],
            "customer_id": chosen["customer_id"],
            "merchant_id": chosen["merchant_id"],
            "device_id": chosen["device_id"],
            "ip_id": chosen["ip_id"],
            "beneficiary_id": chosen["beneficiary_id"],
            "account_age_days": chosen["account_age_days"],
            "failed_auth_count": 0.0,
            "fraud_label": 0,
            "attack_family": "",
            "hour_of_day": hours,
        }
    )
    out["timestamp"] = out["timestamp"].to_numpy() + hours * 0  # keep hour_of_day independent of ts for sampling
    out["hour_of_day"] = (out["timestamp"] % 86400.0) / 3600.0
    return add_behavior_features(out)
