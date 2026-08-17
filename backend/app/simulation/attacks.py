"""Deterministic attack overlays. Each family mutates only its dimensions."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from app.core.config import ATTACK_FAMILIES, RANDOM_STATE
from app.data.ingest import add_behavior_features
from app.simulation.legit import fit_profiles, generate_legitimate
from app.simulation.p2_attacks import P2_APPLY, generate_p2_attacks, p2_attack_catalog

INTENSITY = {
    "low": 0.6,
    "medium": 1.0,
    "high": 1.6,
}


def _scale(intensity: str) -> float:
    return INTENSITY.get((intensity or "medium").lower(), 1.0)


def apply_account_takeover(df: pd.DataFrame, rng: np.random.Generator, intensity: str) -> pd.DataFrame:
    out = df.copy()
    k = _scale(intensity)
    n = len(out)
    out["device_id"] = [f"ato-dev-{rng.integers(10_000, 99_999)}" for _ in range(n)]
    out["ip_id"] = [f"ato-ip-{rng.integers(10_000, 99_999)}" for _ in range(n)]
    out["country"] = np.clip(out["country"] + rng.choice([10.0, -15.0, 30.0], size=n), 1.0, 250.0)
    out["transaction_count_1h"] = np.maximum(out["transaction_count_1h"], 3.0) * (2.0 * k)
    out["transaction_count_24h"] = np.maximum(out["transaction_count_24h"], 6.0) * (2.2 * k)
    out["amount"] = out["amount"] * (2.4 * k)
    out["amount_deviation"] = (out["amount"] / out["avg_amount_30d"].clip(lower=0.01)) - 1.0
    out["failed_auth_count"] = np.clip(rng.integers(1, max(2, int(4 * k) + 1), size=n).astype(float), 1.0, 8.0)
    out["device_age_days"] = 0.0
    out["attack_family"] = "account_takeover"
    out["fraud_label"] = 1
    return out


def apply_velocity_attack(df: pd.DataFrame, rng: np.random.Generator, intensity: str) -> pd.DataFrame:
    out = df.copy()
    k = _scale(intensity)
    out["transaction_count_1h"] = np.maximum(out["transaction_count_1h"], 1.0) * (5.0 * k)
    out["transaction_count_24h"] = np.maximum(out["transaction_count_24h"], 2.0) * (6.0 * k)
    out["merchant_count_24h"] = np.maximum(out["merchant_count_24h"], 1.0) * (4.0 * k)
    out["timestamp"] = out["timestamp"] + rng.uniform(0, 90, size=len(out))
    out["hour_of_day"] = (out["timestamp"] % 86400.0) / 3600.0
    out["attack_family"] = "velocity_attack"
    out["fraud_label"] = 1
    return out


def apply_amount_anomaly(df: pd.DataFrame, rng: np.random.Generator, intensity: str) -> pd.DataFrame:
    out = df.copy()
    k = _scale(intensity)
    out["amount"] = out["avg_amount_30d"].clip(lower=1.0) * (8.0 * k) * rng.uniform(0.9, 1.2, size=len(out))
    out["amount_deviation"] = (out["amount"] / out["avg_amount_30d"].clip(lower=0.01)) - 1.0
    out["attack_family"] = "amount_anomaly"
    out["fraud_label"] = 1
    return out


def apply_beneficiary_anomaly(df: pd.DataFrame, rng: np.random.Generator, intensity: str) -> pd.DataFrame:
    out = df.copy()
    k = _scale(intensity)
    n = len(out)
    out["beneficiary_id"] = [f"new-ben-{rng.integers(1000, 9999)}" for _ in range(n)]
    out["beneficiary_is_new"] = 1.0
    out["destination_concentration"] = np.clip(0.75 + 0.15 * k + rng.uniform(0, 0.1, size=n), 0.0, 1.0)
    out["merchant_id"] = [f"new-merch-{rng.integers(1000, 9999)}" for _ in range(n)]
    out["attack_family"] = "beneficiary_anomaly"
    out["fraud_label"] = 1
    return out


def apply_low_and_slow(df: pd.DataFrame, rng: np.random.Generator, intensity: str) -> pd.DataFrame:
    """Keep amount, device, and geo. Shift sequence / timing / cumulative dest use."""
    out = df.copy()
    k = _scale(intensity)
    # small timing drift only — amounts stay in-band
    out["timestamp"] = out["timestamp"] + rng.uniform(20_000, 40_000, size=len(out)) * k
    out["hour_of_day"] = ((out["hour_of_day"] + 3.5 * k) % 24.0)
    out["destination_concentration"] = np.clip(out["destination_concentration"] + 0.18 * k, 0.0, 0.95)
    out["transaction_count_24h"] = out["transaction_count_24h"] + 1.0 * k
    out["attack_family"] = "low_and_slow"
    out["fraud_label"] = 1
    return out


APPLY = {
    "account_takeover": apply_account_takeover,
    "velocity_attack": apply_velocity_attack,
    "amount_anomaly": apply_amount_anomaly,
    "beneficiary_anomaly": apply_beneficiary_anomaly,
    "low_and_slow": apply_low_and_slow,
    **P2_APPLY,
}


def generate_attacks(
    payments: pd.DataFrame,
    attack_id: str,
    transaction_count: int,
    seed: int = RANDOM_STATE,
    intensity: str = "medium",
) -> pd.DataFrame:
    family = attack_id if attack_id in APPLY else {
        "ATO_001": "account_takeover",
        "VEL_001": "velocity_attack",
        "AMT_001": "amount_anomaly",
        "BEN_001": "beneficiary_anomaly",
        "LOW_AND_SLOW_FRAUD": "low_and_slow",
        "low_and_slow_fraud": "low_and_slow",
        "MUL-001": "mule_network",
        "DEV-001": "shared_device",
        "IP-001": "shared_ip",
        "GEO-001": "geo_anomaly",
        "CTX-001": "combined_context",
    }.get(attack_id, attack_id)
    if family in P2_APPLY:
        return generate_p2_attacks(payments, family, transaction_count, seed=seed, intensity=intensity)
    if family not in APPLY:
        raise ValueError(f"Unknown attack: {attack_id}")
    profiles = fit_profiles(payments)
    base = generate_legitimate(profiles, transaction_count, seed=seed)
    rng = np.random.default_rng(seed)
    mutated = APPLY[family](base, rng, intensity)
    mutated["transaction_id"] = [f"{family}-{seed}-{i}" for i in range(len(mutated))]
    return mutated


def generate_mixed_attacks(payments: pd.DataFrame, n_each: int, seed: int = RANDOM_STATE) -> pd.DataFrame:
    parts = [
        generate_attacks(payments, family, n_each, seed=seed + i, intensity="medium")
        for i, family in enumerate(ATTACK_FAMILIES)
    ]
    return pd.concat(parts, ignore_index=True)


def attack_catalog() -> list[dict[str, Any]]:
    p0 = [
        {"id": "account_takeover", "name": "Account takeover", "tier": "P0", "mutates": ["device", "ip", "geo", "velocity", "amount", "failed_auth_count"]},
        {"id": "velocity_attack", "name": "Velocity attack", "tier": "P0", "mutates": ["transaction_count", "spacing", "merchant_count"]},
        {"id": "amount_anomaly", "name": "Amount anomaly", "tier": "P0", "mutates": ["amount", "amount_deviation"]},
        {"id": "beneficiary_anomaly", "name": "Beneficiary anomaly", "tier": "P0", "mutates": ["beneficiary_id", "destination_concentration"]},
        {"id": "low_and_slow", "name": "Low-and-slow", "tier": "P0", "mutates": ["timing", "sequence", "destination_concentration"]},
    ]
    return p0 + p2_attack_catalog()
