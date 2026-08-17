from __future__ import annotations

from pathlib import Path

import pytest

from app.core.config import IEEE_DIR
from app.data.ingest import load_raw, locate_ieee


def test_ieee_join_and_rate() -> None:
    try:
        root = locate_ieee(IEEE_DIR)
    except FileNotFoundError:
        pytest.skip("IEEE files not on disk")
    assert (root / "train_transaction.csv").exists()
    raw = load_raw(root, sample_n=2000, seed=1)
    assert len(raw) == 2000
    assert not raw["TransactionID"].duplicated().any()
    full_tx = Path(root / "train_transaction.csv")
    assert full_tx.stat().st_size > 1_000_000
    rate = float(raw["isFraud"].mean())
    assert 0.02 < rate < 0.06
