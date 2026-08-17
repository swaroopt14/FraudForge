"""Parameterized mutation engine. No LLM. Seeded only."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from app.threats.schema import MutationParams

_FLIP = {"W": "C", "C": "H", "H": "R", "R": "S", "S": "W"}


def apply_mutation(
    df: pd.DataFrame,
    params: MutationParams,
    rng: np.random.Generator,
    family: str,
) -> pd.DataFrame:
    out = df.copy()
    n = len(out)
    if n == 0:
        out["attack_family"] = family
        out["fraud_label"] = 1
        return out

    def _assign_clusters(prefix: str, count: int) -> list[str]:
        k = max(1, int(count))
        ids = [f"{prefix}-{rng.integers(1000, 9999)}-{i}" for i in range(k)]
        return [ids[int(rng.integers(0, k))] for _ in range(n)]

    if params.device_change_probability > 0:
        mask = rng.random(n) < params.device_change_probability
        new_ids = [f"mut-dev-{rng.integers(10_000, 99_999)}" for _ in range(int(mask.sum()))]
        out.loc[mask, "device_id"] = new_ids
        out.loc[mask, "device_age_days"] = 0.0
    if params.ip_change_probability > 0:
        mask = rng.random(n) < params.ip_change_probability
        out.loc[mask, "ip_id"] = [f"mut-ip-{rng.integers(10_000, 99_999)}" for _ in range(int(mask.sum()))]
    if params.beneficiary_change_probability > 0:
        mask = rng.random(n) < params.beneficiary_change_probability
        out.loc[mask, "beneficiary_id"] = [f"mut-ben-{rng.integers(1000, 9999)}" for _ in range(int(mask.sum()))]
        out.loc[mask, "beneficiary_is_new"] = 1.0
    if params.merchant_change_probability > 0:
        mask = rng.random(n) < params.merchant_change_probability
        out.loc[mask, "merchant_id"] = [f"mut-merch-{rng.integers(1000, 9999)}" for _ in range(int(mask.sum()))]

    if params.share_device:
        out["device_id"] = _assign_clusters("shared-dev", params.cluster_count)
        out["device_age_days"] = 0.0
    if params.share_ip:
        out["ip_id"] = _assign_clusters("shared-ip", params.cluster_count)
    if params.share_merchant:
        out["merchant_id"] = _assign_clusters("shared-merch", params.cluster_count)
    if params.share_beneficiary:
        out["beneficiary_id"] = _assign_clusters("mule-ben", params.cluster_count)
        out["beneficiary_is_new"] = 1.0

    if params.geo_deviation:
        out["country"] = np.clip(out["country"] + params.geo_deviation * rng.choice([-1.0, 1.0], size=n), 1.0, 250.0)
    if params.distance_boost:
        out["distance_from_home"] = out["distance_from_home"] + params.distance_boost

    if params.amount_deviation:
        factor = 1.0 + float(params.amount_deviation)
        jitter = rng.uniform(0.95, 1.05, size=n)
        out["amount"] = (out["avg_amount_30d"].clip(lower=1.0) * factor * jitter).clip(lower=0.01)
        out["amount_deviation"] = (out["amount"] / out["avg_amount_30d"].clip(lower=0.01)) - 1.0

    if params.fragment_parts and params.fragment_parts > 1:
        out["amount"] = (out["amount"] / float(params.fragment_parts)).clip(lower=0.01)
        out["amount_deviation"] = (out["amount"] / out["avg_amount_30d"].clip(lower=0.01)) - 1.0

    if params.velocity_multiplier and params.velocity_multiplier != 1.0:
        k = float(params.velocity_multiplier)
        out["transaction_count_1h"] = np.maximum(out["transaction_count_1h"], 1.0) * k
        out["transaction_count_24h"] = np.maximum(out["transaction_count_24h"], 1.0) * k
        if "txn_count_1m" in out.columns:
            out["txn_count_1m"] = np.maximum(out["txn_count_1m"], 1.0) * k
        if "txn_count_5m" in out.columns:
            out["txn_count_5m"] = np.maximum(out["txn_count_5m"], 1.0) * k
    if params.merchant_count_multiplier and params.merchant_count_multiplier != 1.0:
        out["merchant_count_24h"] = np.maximum(out["merchant_count_24h"], 1.0) * float(params.merchant_count_multiplier)

    if params.failed_auth_boost:
        out["failed_auth_count"] = np.clip(out["failed_auth_count"] + params.failed_auth_boost, 0.0, 12.0)
    if params.hour_shift:
        out["hour_of_day"] = (out["hour_of_day"] + params.hour_shift) % 24.0
        out["timestamp"] = out["timestamp"] + params.hour_shift * 3600.0
    if params.dest_concentration_delta:
        out["destination_concentration"] = np.clip(out["destination_concentration"] + params.dest_concentration_delta, 0.0, 1.0)
    if params.account_age_scale != 1.0:
        out["account_age_days"] = (out["account_age_days"] * float(params.account_age_scale)).clip(lower=0.0)
    if params.category_flip:
        out["merchant_category"] = out["merchant_category"].map(lambda c: _FLIP.get(str(c), "C"))
    if params.spread_seconds and params.spread_seconds > 0:
        offsets = np.linspace(0.0, float(params.spread_seconds), num=n)
        out["timestamp"] = pd.to_numeric(out["timestamp"], errors="coerce").fillna(0.0) + offsets
        out["hour_of_day"] = (out["timestamp"] / 3600.0) % 24.0

    out["attack_family"] = family
    out["fraud_label"] = 1
    from app.data.ingest import refresh_derived_scalars

    return refresh_derived_scalars(out)


def entity_stats(df: pd.DataFrame) -> dict[str, Any]:
    def _nunique(col: str) -> int:
        return int(df[col].nunique()) if col in df.columns and len(df) else 0

    customers = _nunique("customer_id")
    devices = _nunique("device_id")
    ips = _nunique("ip_id")
    merchants = _nunique("merchant_id")
    bens = _nunique("beneficiary_id")
    networks = 0
    if devices and customers and devices < customers:
        networks += 1
    if ips and customers and ips < customers:
        networks += 1
    if bens and customers and bens < max(customers // 4, 1):
        networks += 1
    return {
        "customers": customers,
        "devices": devices,
        "ips": ips,
        "merchants": merchants,
        "beneficiaries": bens,
        "entities": customers + devices + ips + merchants + bens,
        "attack_networks": networks,
    }
