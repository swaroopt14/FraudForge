"""Authorization-time lookup against the lab payment corpus.

Synthetic overlays were computing beneficiary_is_new on the tiny generated
batch, so almost every row looked like a first-time payee — including the
legitimate profile payee. Features must be grounded in customer history.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from app.core.config import NEVER_SEEN_PAIR_HOURS
from app.data.ingest import refresh_derived_scalars


@dataclass
class CorpusHistory:
    pair_n: dict[tuple[str, str], int]
    pair_last: dict[tuple[str, str], float]
    pair_amt: dict[tuple[str, str], float]
    senders: dict[str, int]
    cust_txn: dict[str, int]
    cust_bens: dict[str, int]

    @classmethod
    def from_payments(cls, payments: pd.DataFrame) -> "CorpusHistory":
        if payments is None or not len(payments):
            return cls({}, {}, {}, {}, {}, {})
        work = payments[["customer_id", "beneficiary_id", "timestamp", "amount"]].copy()
        work["customer_id"] = work["customer_id"].astype(str)
        work["beneficiary_id"] = work["beneficiary_id"].astype(str)
        pair = work.groupby(["customer_id", "beneficiary_id"], sort=False).agg(
            n=("amount", "size"),
            last_ts=("timestamp", "max"),
            amt=("amount", "mean"),
        )
        return cls(
            pair_n={(str(a), str(b)): int(n) for (a, b), n in pair["n"].items()},
            pair_last={(str(a), str(b)): float(ts) for (a, b), ts in pair["last_ts"].items()},
            pair_amt={(str(a), str(b)): float(v) for (a, b), v in pair["amt"].items()},
            senders=work.groupby("beneficiary_id")["customer_id"].nunique().astype(int).to_dict(),
            cust_txn=work.groupby("customer_id").size().astype(int).to_dict(),
            cust_bens=work.groupby("customer_id")["beneficiary_id"].nunique().astype(int).to_dict(),
        )

    def attach(self, rows: pd.DataFrame, *, refresh_concentration: bool = False) -> pd.DataFrame:
        """Refresh beneficiary columns from corpus + current batch. Does not invent graph embeddings."""
        if rows is None or not len(rows):
            return rows
        out = rows.copy()
        customers = out["customer_id"].astype(str).to_numpy()
        bens = out["beneficiary_id"].astype(str).to_numpy()
        ts = pd.to_numeric(out.get("timestamp", 0.0), errors="coerce").fillna(0.0).to_numpy()
        amount = pd.to_numeric(out["amount"], errors="coerce").fillna(0.01).to_numpy()
        keys = list(zip(customers, bens))
        pair_n = np.fromiter((self.pair_n.get(k, 0) for k in keys), dtype=float, count=len(keys))
        pair_last = np.fromiter((self.pair_last.get(k, 0.0) for k in keys), dtype=float, count=len(keys))
        pair_amt = np.fromiter((self.pair_amt.get(k, 0.0) for k in keys), dtype=float, count=len(keys))
        corpus_senders = np.fromiter((self.senders.get(b, 0) for b in bens), dtype=float, count=len(bens))
        cust_n = np.fromiter((self.cust_txn.get(c, 0) for c in customers), dtype=float, count=len(customers))
        cust_bens = np.fromiter((self.cust_bens.get(c, 0) for c in customers), dtype=float, count=len(customers))
        is_new = (pair_n <= 0).astype(float)
        batch_senders = out.groupby("beneficiary_id")["customer_id"].transform("nunique").to_numpy(dtype=float)
        sender_count = np.where(corpus_senders > 0, corpus_senders, batch_senders)
        hours = np.where(
            is_new > 0,
            NEVER_SEEN_PAIR_HOURS,
            np.clip((ts - pair_last) / 3600.0, 0.0, NEVER_SEEN_PAIR_HOURS),
        )
        pair_dev = np.where(pair_amt > 0, (amount / np.clip(pair_amt, 0.01, None)) - 1.0, 0.0)
        out["beneficiary_is_new"] = is_new
        out["beneficiary_frequency"] = pair_n + 1.0
        out["customer_beneficiary_count"] = cust_bens + is_new
        out["beneficiary_sender_count"] = sender_count
        out["hours_since_pair"] = hours
        out["pair_amount_deviation"] = pair_dev
        if refresh_concentration:
            out["destination_concentration"] = ((pair_n + 1.0) / np.clip(cust_n + 1.0, 1.0, None)).clip(0.0, 1.0)
        return refresh_derived_scalars(out)

    def enrich(self, df: pd.DataFrame) -> pd.DataFrame:
        """Fill V012 columns on corpus rows without flipping beneficiary_is_new."""
        if df is None or not len(df):
            return df
        out = df.copy()
        customers = out["customer_id"].astype(str).to_numpy()
        bens = out["beneficiary_id"].astype(str).to_numpy()
        ts = pd.to_numeric(out.get("timestamp", 0.0), errors="coerce").fillna(0.0).to_numpy()
        amount = pd.to_numeric(out["amount"], errors="coerce").fillna(0.01).to_numpy()
        keys = list(zip(customers, bens))
        pair_last = np.fromiter((self.pair_last.get(k, 0.0) for k in keys), dtype=float, count=len(keys))
        pair_amt = np.fromiter((self.pair_amt.get(k, 0.0) for k in keys), dtype=float, count=len(keys))
        out["beneficiary_sender_count"] = np.fromiter((self.senders.get(b, 1) for b in bens), dtype=float, count=len(bens))
        hours = np.clip((ts - pair_last) / 3600.0, 0.0, NEVER_SEEN_PAIR_HOURS)
        if "beneficiary_is_new" in out.columns:
            is_new = pd.to_numeric(out["beneficiary_is_new"], errors="coerce").fillna(0.0).to_numpy()
            hours = np.where(is_new > 0, NEVER_SEEN_PAIR_HOURS, hours)
        out["hours_since_pair"] = hours
        out["pair_amount_deviation"] = np.where(pair_amt > 0, (amount / np.clip(pair_amt, 0.01, None)) - 1.0, 0.0)
        return refresh_derived_scalars(out)
