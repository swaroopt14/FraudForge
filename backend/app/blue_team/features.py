"""P2 observable context + network features. No label leakage."""

from __future__ import annotations

import pandas as pd

from app.core.config import FEATURE_COLUMNS, FEATURE_COLUMNS_V020, LEAKAGE_COLUMNS


def _series(df: pd.DataFrame, name: str, default: float = 0.0) -> pd.Series:
    if name in df.columns:
        return pd.to_numeric(df[name], errors="coerce").fillna(default)
    return pd.Series(default, index=df.index, dtype=float)


def attach_p2_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add geo / device / IP / beneficiary / graph columns from the payment stream only."""
    extra = [c for c in FEATURE_COLUMNS_V020 if c not in FEATURE_COLUMNS]
    if extra and all(col in df.columns for col in extra):
        return df.copy()
    out = df.copy()
    n = len(out)
    if n == 0:
        for col in FEATURE_COLUMNS_V020:
            if col not in out.columns:
                out[col] = 0.0
        return out

    cust = out["customer_id"].astype(str) if "customer_id" in out.columns else pd.Series(["unk"] * n, index=out.index)
    device = out["device_id"].astype(str) if "device_id" in out.columns else pd.Series(["unk"] * n, index=out.index)
    ip = out["ip_id"].astype(str) if "ip_id" in out.columns else pd.Series(["unk"] * n, index=out.index)
    ben = out["beneficiary_id"].astype(str) if "beneficiary_id" in out.columns else pd.Series(["unk"] * n, index=out.index)
    ts = _series(out, "timestamp")
    country = _series(out, "country", 87.0)
    dist = _series(out, "distance_from_home")

    work = pd.DataFrame(
        {
            "customer_id": cust,
            "timestamp": ts,
            "country": country,
            "distance_from_home": dist,
        },
        index=out.index,
    ).sort_values(["customer_id", "timestamp"])
    prev_country = work.groupby("customer_id", sort=False)["country"].shift(1)
    prev_dist = work.groupby("customer_id", sort=False)["distance_from_home"].shift(1)
    prev_ts = work.groupby("customer_id", sort=False)["timestamp"].shift(1)
    country_delta = (work["country"] - prev_country).abs().fillna(0.0)
    dist_delta = (work["distance_from_home"] - prev_dist).abs().fillna(0.0)
    dt = (work["timestamp"] - prev_ts).fillna(10_000.0).clip(lower=1.0)
    impossible = ((country_delta >= 20.0) & (dt <= 7_200.0)).astype(float)
    geo = pd.DataFrame(
        {
            "geo_country_delta": country_delta,
            "geo_distance_delta": dist_delta,
            "geo_impossible_travel": impossible,
        },
        index=work.index,
    ).reindex(out.index)

    device_accounts = cust.groupby(device).transform(lambda s: float(s.nunique()))
    ip_accounts = cust.groupby(ip).transform(lambda s: float(s.nunique()))
    fan_in = cust.groupby(ben).transform(lambda s: float(s.nunique()))
    ben_txn = ben.groupby(ben).transform("size").astype(float)
    n_cust = max(float(cust.nunique()), 1.0)
    ben_share = fan_in / n_cust
    device_shared = (device_accounts >= 3.0).astype(float)
    ip_shared = (ip_accounts >= 3.0).astype(float)
    degree = (fan_in / 20.0).clip(0, 1) + (device_accounts / 10.0).clip(0, 1) + (ip_accounts / 10.0).clip(0, 1)
    mule = (
        (fan_in >= 8.0).astype(float) * 0.5
        + device_shared * 0.25
        + ip_shared * 0.25
    ).clip(0, 1)

    out["geo_country_delta"] = geo["geo_country_delta"].to_numpy()
    out["geo_impossible_travel"] = geo["geo_impossible_travel"].to_numpy()
    out["geo_distance_delta"] = geo["geo_distance_delta"].to_numpy()
    out["device_account_count"] = device_accounts.to_numpy()
    out["device_is_shared"] = device_shared.to_numpy()
    out["ip_account_count"] = ip_accounts.to_numpy()
    out["ip_is_shared"] = ip_shared.to_numpy()
    out["beneficiary_fan_in"] = fan_in.to_numpy()
    out["beneficiary_txn_count"] = ben_txn.to_numpy()
    out["beneficiary_customer_share"] = ben_share.to_numpy()
    out["network_degree"] = degree.to_numpy()
    out["mule_cluster_score"] = mule.to_numpy()
    return out


def feature_matrix_v020(df: pd.DataFrame) -> pd.DataFrame:
    work = attach_p2_features(df)
    for col in LEAKAGE_COLUMNS:
        if col in work.columns:
            work = work.drop(columns=[col])
    for col in FEATURE_COLUMNS_V020:
        if col not in work.columns:
            work[col] = 0.0
    leaked = [c for c in LEAKAGE_COLUMNS if c in FEATURE_COLUMNS_V020]
    if leaked:
        raise RuntimeError(f"label leakage in FEATURE_COLUMNS_V020: {leaked}")
    return work[FEATURE_COLUMNS_V020].apply(pd.to_numeric, errors="coerce").fillna(0.0).astype(float)


def geo_risk(row: pd.Series) -> float:
    return float(
        max(
            float(row.get("geo_impossible_travel") or 0.0),
            min(1.0, float(row.get("geo_country_delta") or 0.0) / 40.0),
        )
    )


def device_risk(row: pd.Series) -> float:
    shared = float(row.get("device_is_shared") or 0.0)
    count = min(1.0, max(0.0, (float(row.get("device_account_count") or 1.0) - 1.0) / 12.0))
    return max(shared, count)


def ip_risk(row: pd.Series) -> float:
    shared = float(row.get("ip_is_shared") or 0.0)
    count = min(1.0, max(0.0, (float(row.get("ip_account_count") or 1.0) - 1.0) / 12.0))
    return max(shared, count)


def beneficiary_risk(row: pd.Series) -> float:
    fan = min(1.0, float(row.get("beneficiary_fan_in") or 0.0) / 25.0)
    share = min(1.0, float(row.get("beneficiary_customer_share") or 0.0) * 4.0)
    return max(fan, share)


def network_risk(row: pd.Series) -> float:
    return float(
        max(
            float(row.get("mule_cluster_score") or 0.0),
            min(1.0, float(row.get("network_degree") or 0.0) / 2.0),
        )
    )
