from __future__ import annotations

from app.data.ingest import attach_merchant_risk
from app.data.schema import REQUIRED_COLUMNS, PaymentIn


def test_schema_and_labels(payments) -> None:
    for col in REQUIRED_COLUMNS:
        assert col in payments.columns
    assert payments["transaction_id"].is_unique
    assert (payments["amount"] > 0).all()
    assert payments["timestamp"].notna().all()
    assert set(payments["fraud_label"].unique()) <= {0, 1}
    required = ["amount", "customer_id", "merchant_id", "device_id", "fraud_label"]
    assert payments[required].isna().sum().sum() == 0
    PaymentIn.model_validate(payments.iloc[0].to_dict())
    rate = float(payments["fraud_label"].mean())
    assert 0.001 < rate < 0.25
    assert len(payments) >= 200


def test_merchant_risk_train_split_only(payments) -> None:
    assert "merchant_risk" in payments.columns
    # ingest leaves zeros; rates come from the train split only
    assert (payments["merchant_risk"] == 0).all()
    mid = len(payments) // 2
    train, hold = payments.iloc[:mid], payments.iloc[mid:]
    tagged = attach_merchant_risk(train, hold)
    assert tagged["merchant_risk"].min() >= 0
    assert tagged["merchant_risk"].max() <= 1
