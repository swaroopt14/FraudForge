"""IEEE-CIS → normalized payments parquet."""

from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import pandas as pd

from app.core.config import (
    FEATURE_COLUMNS,
    FEATURE_COLUMNS_V011,
    IEEE_DIR,
    IEEE_SAMPLE_N,
    LAB_ROOT,
    NEVER_SEEN_PAIR_HOURS,
    PAYMENTS_PATH,
    RANDOM_STATE,
    RAW_DIR,
    ensure_dirs,
)

TX_COLS = [
    "TransactionID",
    "isFraud",
    "TransactionDT",
    "TransactionAmt",
    "ProductCD",
    "card1",
    "card4",
    "card6",
    "addr1",
    "addr2",
    "dist1",
    "D1",
    "C1",
    "C2",
]
ID_COLS = ["TransactionID", "DeviceType", "DeviceInfo", "id_31"]


def _stable_id(*parts: object) -> str:
    blob = "|".join("" if p is None or (isinstance(p, float) and np.isnan(p)) else str(p) for p in parts)
    return hashlib.sha1(blob.encode("utf-8")).hexdigest()[:12]


def locate_ieee(ieee_dir: Path | None = None) -> Path:
    candidates = [
        ieee_dir,
        IEEE_DIR,
        RAW_DIR,
        LAB_ROOT / "data" / "ieee-fraud-detection",
        Path(__file__).resolve().parents[4] / "data" / "ieee-fraud-detection",
    ]
    for path in candidates:
        if path and (path / "train_transaction.csv").exists():
            return path
    raise FileNotFoundError("IEEE train_transaction.csv not found. Set IEEE_DIR.")


def load_raw(ieee_dir: Path | None = None, sample_n: int | None = None, seed: int = RANDOM_STATE) -> pd.DataFrame:
    root = locate_ieee(ieee_dir)
    tx_path = root / "train_transaction.csv"
    id_path = root / "train_identity.csv"
    n = int(sample_n if sample_n is not None else IEEE_SAMPLE_N)

    tx = pd.read_csv(tx_path, usecols=TX_COLS)
    if n and n < len(tx):
        fraud = tx.loc[tx["isFraud"] == 1]
        legit = tx.loc[tx["isFraud"] == 0]
        n_fraud = max(1, int(round(n * (len(fraud) / len(tx)))))
        n_legit = n - n_fraud
        rng = np.random.default_rng(seed)
        fraud_idx = rng.choice(fraud.index.to_numpy(), size=min(n_fraud, len(fraud)), replace=False)
        legit_idx = rng.choice(legit.index.to_numpy(), size=min(n_legit, len(legit)), replace=False)
        tx = tx.loc[np.concatenate([fraud_idx, legit_idx])].copy()

    ident = pd.read_csv(id_path, usecols=ID_COLS)
    merged = tx.merge(ident, on="TransactionID", how="left")
    if merged["TransactionID"].duplicated().any():
        raise ValueError("Join duplicated TransactionID")
    return merged.reset_index(drop=True)


def normalize(raw: pd.DataFrame) -> pd.DataFrame:
    work = raw.copy()
    card1 = work["card1"].fillna(0).astype(int)
    product = work["ProductCD"].fillna("W").astype(str)
    addr1 = work["addr1"].fillna(0)
    device_raw = work.get("DeviceInfo", pd.Series([""] * len(work))).fillna("")
    browser = work.get("id_31", pd.Series([""] * len(work))).fillna("")
    device_key = np.where(device_raw.astype(str).str.len() > 0, device_raw.astype(str), browser.astype(str))
    device_key = np.where(pd.Series(device_key).str.len() > 0, device_key, "unknown")

    out = pd.DataFrame(
        {
            "transaction_id": work["TransactionID"].astype(str),
            "timestamp": pd.to_numeric(work["TransactionDT"], errors="coerce").fillna(0.0),
            "amount": pd.to_numeric(work["TransactionAmt"], errors="coerce").clip(lower=0.01),
            "merchant_category": product,
            "payment_method": (
                work["card4"].fillna("unknown").astype(str) + "_" + work["card6"].fillna("unknown").astype(str)
            ),
            "country": pd.to_numeric(work["addr2"], errors="coerce").fillna(87.0),
            "distance_from_home": pd.to_numeric(work["dist1"], errors="coerce"),
            "customer_id": [_stable_id("c", int(v)) for v in card1],
            "merchant_id": [_stable_id("m", p, int(c) // 100) for p, c in zip(product, card1)],
            "device_id": [_stable_id("d", d) for d in device_key],
            "ip_id": [_stable_id("ip", d, a) for d, a in zip(device_key, addr1)],
            "beneficiary_id": [_stable_id("b", p, int(c) // 50) for p, c in zip(product, card1)],
            "account_age_days": pd.to_numeric(work["D1"], errors="coerce").fillna(0.0).clip(lower=0.0),
            "failed_auth_count": 0.0,
            "fraud_label": pd.to_numeric(work["isFraud"], errors="coerce").fillna(0).astype(int),
            "attack_family": "",
        }
    )
    dist_med = float(out["distance_from_home"].median()) if out["distance_from_home"].notna().any() else 0.0
    out["distance_from_home"] = out["distance_from_home"].fillna(dist_med)
    out["hour_of_day"] = (out["timestamp"] % 86400.0) / 3600.0
    return add_behavior_features(out)


def add_behavior_features(df: pd.DataFrame) -> pd.DataFrame:
    work = df.sort_values(["customer_id", "timestamp"]).copy()
    grp = work.groupby("customer_id", sort=False)
    work["transaction_count_1h"] = grp["timestamp"].transform(lambda s: _rolling_count(s, 3600))
    work["transaction_count_24h"] = grp["timestamp"].transform(lambda s: _rolling_count(s, 86400))
    work["avg_amount_30d"] = grp["amount"].transform(lambda s: s.expanding().mean().shift(1)).fillna(work["amount"])
    work["amount_deviation"] = (work["amount"] / work["avg_amount_30d"].clip(lower=0.01)) - 1.0
    first_dev = work.groupby("device_id")["timestamp"].transform("min")
    work["device_age_days"] = ((work["timestamp"] - first_dev) / 86400.0).clip(lower=0.0)
    work["merchant_count_24h"] = grp["merchant_id"].transform(_expanding_nunique)
    dest_counts = work.groupby(["customer_id", "beneficiary_id"])["transaction_id"].transform("count")
    cust_counts = work.groupby("customer_id")["transaction_id"].transform("count")
    work["destination_concentration"] = (dest_counts / cust_counts.clip(lower=1)).clip(0.0, 1.0)
    first_ben = work.groupby(["customer_id", "beneficiary_id"])["timestamp"].transform("min")
    work["beneficiary_is_new"] = (work["timestamp"] == first_ben).astype(float)
    work["merchant_risk"] = 0.0
    return work.reset_index(drop=True)


def _expanding_nunique(values: pd.Series) -> pd.Series:
    seen: dict[str, None] = {}
    out = np.empty(len(values), dtype=float)
    for i, value in enumerate(values.to_numpy()):
        seen[str(value)] = None
        out[i] = len(seen)
    return pd.Series(out, index=values.index)


def _rolling_count(times: pd.Series, window: float) -> pd.Series:
    values = times.to_numpy(dtype=float)
    out = np.ones(len(values), dtype=float)
    j = 0
    for i, t in enumerate(values):
        while values[j] < t - window:
            j += 1
        out[i] = i - j + 1
    return pd.Series(out, index=times.index)


def refresh_derived_scalars(df: pd.DataFrame) -> pd.DataFrame:
    """Authorization-time scalars from columns already on the row. Safe after mutations."""
    work = df.copy()
    amount = pd.to_numeric(work["amount"], errors="coerce").fillna(0.01).clip(lower=0.01)
    hour = pd.to_numeric(work.get("hour_of_day", 12.0), errors="coerce").fillna(12.0)
    avg = pd.to_numeric(work.get("avg_amount_30d", amount), errors="coerce").fillna(amount).clip(lower=0.01)
    std = pd.to_numeric(work.get("customer_std_amount", 0.0), errors="coerce").fillna(0.0)
    work["log_amount"] = np.log1p(amount)
    work["amount_zscore"] = (amount - avg) / std.clip(lower=1e-3)
    work["hour_sin"] = np.sin(2.0 * np.pi * hour / 24.0)
    work["hour_cos"] = np.cos(2.0 * np.pi * hour / 24.0)
    if "beneficiary_is_new" in work.columns:
        is_new = pd.to_numeric(work["beneficiary_is_new"], errors="coerce").fillna(0.0).clip(0.0, 1.0)
        if "customer_beneficiary_count" in work.columns:
            counts = pd.to_numeric(work["customer_beneficiary_count"], errors="coerce").fillna(0.0).clip(lower=0.0)
            work["payee_novelty"] = is_new * np.log1p(counts)
        if "hours_since_pair" in work.columns:
            hours = pd.to_numeric(work["hours_since_pair"], errors="coerce").fillna(0.0)
            work["hours_since_pair"] = np.where(is_new > 0, NEVER_SEEN_PAIR_HOURS, hours)
    return work


def add_v011_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add BLUE-0.1.1 columns without rewriting frozen FEATURE_COLUMNS values."""
    extra = [c for c in FEATURE_COLUMNS_V011 if c not in FEATURE_COLUMNS]
    if extra and set(extra).issubset(df.columns):
        return refresh_derived_scalars(df)
    work = df.copy()
    work["_row"] = np.arange(len(work))
    sorted_w = work.sort_values(["customer_id", "timestamp"], kind="mergesort")
    grp = sorted_w.groupby("customer_id", sort=False)
    sorted_w["txn_count_1m"] = grp["timestamp"].transform(lambda s: _rolling_count(s, 60.0))
    sorted_w["txn_count_5m"] = grp["timestamp"].transform(lambda s: _rolling_count(s, 300.0))
    sorted_w["customer_std_amount"] = grp["amount"].transform(lambda s: s.expanding().std().shift(1)).fillna(0.0)
    sorted_w["customer_beneficiary_count"] = grp["beneficiary_id"].transform(_expanding_nunique)
    sorted_w["beneficiary_frequency"] = sorted_w.groupby(["customer_id", "beneficiary_id"]).cumcount() + 1
    sorted_w["customer_merchant_frequency"] = sorted_w.groupby(["customer_id", "merchant_id"]).cumcount() + 1
    by_merchant = sorted_w.sort_values(["merchant_id", "timestamp"], kind="mergesort")
    by_merchant["merchant_avg_amount"] = (
        by_merchant.groupby("merchant_id")["amount"].transform(lambda s: s.expanding().mean().shift(1)).fillna(by_merchant["amount"])
    )
    sorted_w["merchant_avg_amount"] = by_merchant["merchant_avg_amount"].reindex(sorted_w.index)
    sorted_w = refresh_derived_scalars(sorted_w)
    aligned = sorted_w.sort_values("_row", kind="mergesort")
    out = df.copy()
    for col in extra:
        out[col] = aligned[col].to_numpy()
    return out.drop(columns=["_row"], errors="ignore")


def attach_merchant_risk(train: pd.DataFrame, apply_to: pd.DataFrame) -> pd.DataFrame:
    """Train-split only fraud rate. No future leakage onto the rate table."""
    rates = train.groupby("merchant_id")["fraud_label"].mean()
    global_rate = float(train["fraud_label"].mean()) if len(train) else 0.03
    out = apply_to.copy()
    out["merchant_risk"] = out["merchant_id"].map(rates).fillna(global_rate).astype(float)
    return out


def ingest(ieee_dir: Path | None = None, sample_n: int | None = None, persist: bool = True) -> pd.DataFrame:
    ensure_dirs()
    raw = load_raw(ieee_dir, sample_n=sample_n)
    payments = normalize(raw)
    if persist:
        PAYMENTS_PATH.parent.mkdir(parents=True, exist_ok=True)
        payments.to_parquet(PAYMENTS_PATH, index=False)
    return payments


def load_payments() -> pd.DataFrame:
    if PAYMENTS_PATH.exists():
        frame = pd.read_parquet(PAYMENTS_PATH)
        extra = [c for c in FEATURE_COLUMNS_V011 if c not in FEATURE_COLUMNS]
        if extra and not set(extra).issubset(frame.columns):
            frame = add_v011_features(frame)
        if "beneficiary_sender_count" not in frame.columns or "hours_since_pair" not in frame.columns:
            from app.data.history import CorpusHistory

            frame = CorpusHistory.from_payments(frame).enrich(frame)
        if "payee_novelty" not in frame.columns:
            frame = refresh_derived_scalars(frame)
        return frame
    return ingest()
