"""P2 coordinated / contextual attack overlays. Individual rows can look legitimate."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from app.core.config import P2_ATTACK_FAMILIES, RANDOM_STATE
from app.simulation.legit import fit_profiles, generate_legitimate

INTENSITY = {"low": 0.6, "medium": 1.0, "high": 1.6}


def _scale(intensity: str) -> float:
    return INTENSITY.get((intensity or "medium").lower(), 1.0)


def _keep_spend_quiet(out: pd.DataFrame) -> pd.DataFrame:
    """Look individually legitimate: no amount/velocity spike."""
    out["amount"] = out["avg_amount_30d"].clip(lower=5.0) * 0.95
    out["amount_deviation"] = (out["amount"] / out["avg_amount_30d"].clip(lower=0.01)) - 1.0
    out["transaction_count_1h"] = np.minimum(out["transaction_count_1h"].clip(lower=1.0), 2.0)
    out["transaction_count_24h"] = np.minimum(out["transaction_count_24h"].clip(lower=1.0), 4.0)
    out["failed_auth_count"] = 0.0
    return out


def apply_mule_network(df: pd.DataFrame, rng: np.random.Generator, intensity: str) -> pd.DataFrame:
    """Many accounts → 1–2 beneficiaries. Amounts stay in-band."""
    out = _keep_spend_quiet(df.copy())
    k = _scale(intensity)
    n = len(out)
    n_ben = 2 if n >= 20 else 1
    bens = [f"mule-ben-{i}" for i in range(n_ben)]
    out["beneficiary_id"] = [bens[i % n_ben] for i in range(n)]
    out["beneficiary_is_new"] = 0.0
    out["destination_concentration"] = np.clip(0.18 + 0.04 * k, 0.0, 0.35)
    n_dev = max(2, int(3 * k))
    n_ip = max(2, int(3 * k))
    out["device_id"] = [f"mule-dev-{i % n_dev}" for i in range(n)]
    out["ip_id"] = [f"mule-ip-{i % n_ip}" for i in range(n)]
    out["customer_id"] = [f"mule-cust-{i}" for i in range(n)]
    out["attack_family"] = "mule_network"
    out["fraud_label"] = 1
    out["variant_id"] = "MUL-N03"
    return out


def apply_shared_device(df: pd.DataFrame, rng: np.random.Generator, intensity: str) -> pd.DataFrame:
    out = _keep_spend_quiet(df.copy())
    n = len(out)
    out["device_id"] = "shared-dev-1"
    out["customer_id"] = [f"dev-cust-{i}" for i in range(n)]
    out["device_age_days"] = rng.uniform(30, 400, size=n)
    out["attack_family"] = "shared_device"
    out["fraud_label"] = 1
    out["variant_id"] = "DEV-S01"
    return out


def apply_shared_ip(df: pd.DataFrame, rng: np.random.Generator, intensity: str) -> pd.DataFrame:
    out = _keep_spend_quiet(df.copy())
    n = len(out)
    out["ip_id"] = "shared-ip-1"
    out["customer_id"] = [f"ip-cust-{i}" for i in range(n)]
    out["attack_family"] = "shared_ip"
    out["fraud_label"] = 1
    out["variant_id"] = "IP-S01"
    return out


def apply_geo_anomaly(df: pd.DataFrame, rng: np.random.Generator, intensity: str) -> pd.DataFrame:
    """Same customer: country hops inside an impossible window. Spend stays normal."""
    out = _keep_spend_quiet(df.copy())
    n = len(out)
    hops = np.array([87.0, 826.0, 87.0])  # numeric country codes as stand-ins
    out["customer_id"] = "geo-cust-1"
    out["country"] = hops[np.arange(n) % 3]
    base_ts = float(out["timestamp"].iloc[0]) if n else 0.0
    out["timestamp"] = base_ts + np.arange(n) * 1_800.0
    out["hour_of_day"] = (out["timestamp"] % 86400.0) / 3600.0
    out["distance_from_home"] = np.where(np.arange(n) % 3 == 1, 4_200.0, 12.0)
    out["attack_family"] = "geo_anomaly"
    out["fraud_label"] = 1
    out["variant_id"] = "GEO-T01"
    return out


def apply_combined_context(df: pd.DataFrame, rng: np.random.Generator, intensity: str) -> pd.DataFrame:
    """New beneficiary + shared device + shared IP + geo jump + moderate velocity."""
    out = df.copy()
    k = _scale(intensity)
    n = len(out)
    out["beneficiary_id"] = "combo-ben-1"
    out["beneficiary_is_new"] = 1.0
    out["device_id"] = "combo-dev-1"
    out["ip_id"] = "combo-ip-1"
    out["customer_id"] = [f"combo-cust-{i}" for i in range(n)]
    out["country"] = np.where(np.arange(n) % 2 == 0, 87.0, 826.0)
    out["timestamp"] = float(out["timestamp"].iloc[0]) + np.arange(n) * 2_400.0
    out["transaction_count_1h"] = np.minimum(np.maximum(out["transaction_count_1h"], 2.0) * (1.4 * k), 5.0)
    out["amount"] = out["avg_amount_30d"].clip(lower=5.0) * (1.15 * k)
    out["amount_deviation"] = (out["amount"] / out["avg_amount_30d"].clip(lower=0.01)) - 1.0
    out["attack_family"] = "combined_context"
    out["fraud_label"] = 1
    out["variant_id"] = "CTX-C01"
    return out


P2_APPLY = {
    "mule_network": apply_mule_network,
    "shared_device": apply_shared_device,
    "shared_ip": apply_shared_ip,
    "geo_anomaly": apply_geo_anomaly,
    "combined_context": apply_combined_context,
}

P2_ALIASES = {
    "MUL-001": "mule_network",
    "DEV-001": "shared_device",
    "IP-001": "shared_ip",
    "GEO-001": "geo_anomaly",
    "CTX-001": "combined_context",
}


def generate_p2_attacks(
    payments: pd.DataFrame,
    attack_id: str,
    transaction_count: int,
    seed: int = RANDOM_STATE,
    intensity: str = "medium",
) -> pd.DataFrame:
    family = P2_ALIASES.get(attack_id, attack_id)
    if family not in P2_APPLY:
        raise ValueError(f"Unknown P2 attack: {attack_id}")
    profiles = fit_profiles(payments)
    base = generate_legitimate(profiles, transaction_count, seed=seed)
    rng = np.random.default_rng(seed)
    mutated = P2_APPLY[family](base, rng, intensity)
    mutated["transaction_id"] = [f"{family}-{seed}-{i}" for i in range(len(mutated))]
    mutated["simulation_id"] = ""
    return mutated


def generate_mixed_p2_attacks(payments: pd.DataFrame, n_each: int, seed: int = RANDOM_STATE) -> pd.DataFrame:
    parts = [
        generate_p2_attacks(payments, family, n_each, seed=seed + i, intensity="medium")
        for i, family in enumerate(P2_ATTACK_FAMILIES)
    ]
    return pd.concat(parts, ignore_index=True)


def p2_attack_catalog() -> list[dict[str, Any]]:
    return [
        {"id": "mule_network", "name": "Mule network", "tier": "P2", "mutates": ["beneficiary fan-in", "shared device", "shared IP"]},
        {"id": "shared_device", "name": "Shared device", "tier": "P2", "mutates": ["device-account degree"]},
        {"id": "shared_ip", "name": "Shared IP", "tier": "P2", "mutates": ["IP-account degree"]},
        {"id": "geo_anomaly", "name": "Geographic anomaly", "tier": "P2", "mutates": ["impossible travel"]},
        {"id": "combined_context", "name": "Combined context", "tier": "P2", "mutates": ["beneficiary", "device", "IP", "geo", "velocity"]},
    ]
