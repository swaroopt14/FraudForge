"""Computed fidelity — never hardcoded."""

from __future__ import annotations

import json
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import ks_2samp, wasserstein_distance

from app.core.config import EVAL_DIR, ensure_dirs


def _norm_score(distance: float, scale: float) -> float:
    return float(np.clip(1.0 - distance / max(scale, 1e-9), 0.0, 1.0))


def _js_div(p: pd.Series, q: pd.Series) -> float:
    a = p.value_counts(normalize=True)
    b = q.value_counts(normalize=True)
    idx = sorted(set(a.index) | set(b.index))
    pa = np.array([a.get(i, 0.0) for i in idx], dtype=float)
    pb = np.array([b.get(i, 0.0) for i in idx], dtype=float)
    m = 0.5 * (pa + pb)
    def _kl(x, y):
        mask = (x > 0) & (y > 0)
        return float(np.sum(x[mask] * np.log(x[mask] / y[mask])))
    return 0.5 * _kl(pa, m) + 0.5 * _kl(pb, m)


def fidelity_report(real: pd.DataFrame, synthetic: pd.DataFrame) -> dict[str, Any]:
    amount_wd = wasserstein_distance(real["amount"], synthetic["amount"])
    amount_ks = ks_2samp(real["amount"], synthetic["amount"]).statistic
    time_wd = wasserstein_distance(real["hour_of_day"], synthetic["hour_of_day"])
    vel_col = "transaction_count_24h"
    vel_wd = wasserstein_distance(real[vel_col], synthetic[vel_col])
    merch_js = _js_div(real["merchant_category"], synthetic["merchant_category"])

    amount_s = _norm_score(amount_wd, max(float(real["amount"].std()), 1.0))
    time_s = _norm_score(time_wd, 8.0)
    vel_s = _norm_score(vel_wd, max(float(real[vel_col].std()), 1.0))
    merch_s = _norm_score(merch_js, 1.0)
    weights = {"amount": 0.30, "time": 0.25, "velocity": 0.25, "merchant": 0.20}
    amount_r = round(amount_s, 4)
    time_r = round(time_s, 4)
    vel_r = round(vel_s, 4)
    merch_r = round(merch_s, 4)
    overall = (
        weights["amount"] * amount_r
        + weights["time"] * time_r
        + weights["velocity"] * vel_r
        + weights["merchant"] * merch_r
    )
    payload = {
        "amount_distribution": amount_r,
        "time_distribution": time_r,
        "velocity_distribution": vel_r,
        "merchant_distribution": merch_r,
        "overall_fidelity": float(overall),
        "raw": {
            "amount_wasserstein": float(amount_wd),
            "amount_ks": float(amount_ks),
            "time_wasserstein": float(time_wd),
            "velocity_wasserstein": float(vel_wd),
            "merchant_js": float(merch_js),
        },
        "weights": weights,
    }
    ensure_dirs()
    (EVAL_DIR / "fidelity.json").write_text(json.dumps(payload, indent=2))
    return payload
