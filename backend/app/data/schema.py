"""Pydantic + SQLAlchemy payment models."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator
from sqlalchemy import Float, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


REQUIRED_COLUMNS = [
    "transaction_id",
    "timestamp",
    "amount",
    "customer_id",
    "merchant_id",
    "device_id",
    "fraud_label",
]


class PaymentIn(BaseModel):
    transaction_id: str
    timestamp: float
    amount: float = Field(gt=0)
    merchant_id: str
    merchant_category: str = "W"
    customer_id: str
    device_id: str = "unknown"
    ip_id: str = "unknown"
    beneficiary_id: str = "unknown"
    country: float = 87.0
    payment_method: str = "unknown"
    account_age_days: float = 0.0
    transaction_count_1h: float = 1.0
    transaction_count_24h: float = 1.0
    avg_amount_30d: float = 50.0
    amount_deviation: float = 0.0
    device_age_days: float = 0.0
    failed_auth_count: float = 0.0
    merchant_risk: float = 0.0
    distance_from_home: float = 0.0
    hour_of_day: float = 12.0
    beneficiary_is_new: float = 0.0
    destination_concentration: float = 0.2
    merchant_count_24h: float = 1.0
    fraud_label: int = 0
    attack_family: str = ""

    @field_validator("fraud_label")
    @classmethod
    def _label(cls, value: int) -> int:
        if value not in (0, 1):
            raise ValueError("fraud_label must be 0 or 1")
        return value


class PaymentRow(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(64), index=True)
    transaction_id: Mapped[str] = mapped_column(String(64), index=True)
    attack_family: Mapped[str] = mapped_column(String(64), default="")
    amount: Mapped[float] = mapped_column(Float)
    fraud_probability: Mapped[float] = mapped_column(Float, default=0.0)
    decision: Mapped[str] = mapped_column(String(16), default="ALLOW")
    payload: Mapped[str] = mapped_column(String)


class SimulationRun(Base):
    __tablename__ = "simulation_runs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    attack_family: Mapped[str] = mapped_column(String(64))
    n: Mapped[int] = mapped_column(Integer)
    seed: Mapped[int] = mapped_column(Integer)
    intensity: Mapped[str] = mapped_column(String(16), default="medium")
    report_text: Mapped[str] = mapped_column(String, default="")
    metrics_json: Mapped[str] = mapped_column(String, default="{}")


def row_to_payment(row: dict[str, Any]) -> PaymentIn:
    return PaymentIn.model_validate(row)
