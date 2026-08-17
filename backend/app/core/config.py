"""Runtime paths and thresholds."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

_DEFAULT_LAB = Path(__file__).resolve().parents[3]
LAB_ROOT = Path(os.getenv("LAB_ROOT") or _DEFAULT_LAB)
load_dotenv(LAB_ROOT / ".env")

WORKSPACE_ROOT = LAB_ROOT.parent
DEFAULT_IEEE = WORKSPACE_ROOT / "data" / "ieee-fraud-detection"

IEEE_DIR = Path(os.getenv("IEEE_DIR") or DEFAULT_IEEE)
IEEE_SAMPLE_N = int(os.getenv("IEEE_SAMPLE_N", "80000"))
RANDOM_STATE = int(os.getenv("RANDOM_STATE", "424242"))

DATA_DIR = LAB_ROOT / "data"
RAW_DIR = DATA_DIR / "raw" / "ieee-fraud-detection"
PROCESSED_DIR = DATA_DIR / "processed"
SYNTHETIC_DIR = DATA_DIR / "synthetic"
MODELS_DIR = LAB_ROOT / "models"
EVAL_DIR = LAB_ROOT / "evaluation"
REPORTS_DIR = EVAL_DIR / "reports"
SIM_DIR = LAB_ROOT / "simulations"

PAYMENTS_PATH = PROCESSED_DIR / "payments.parquet"
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DATA_DIR / 'lab.db'}")

ALLOW_THRESHOLD = float(os.getenv("ALLOW_THRESHOLD", "0.30"))
STEP_UP_THRESHOLD = float(os.getenv("STEP_UP_THRESHOLD", "0.60"))
REVIEW_THRESHOLD = float(os.getenv("REVIEW_THRESHOLD", "0.80"))

CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",") if o.strip()]

ATTACK_FAMILIES = [
    "account_takeover",
    "velocity_attack",
    "amount_anomaly",
    "beneficiary_anomaly",
    "low_and_slow",
]

P2_ATTACK_FAMILIES = [
    "mule_network",
    "shared_device",
    "shared_ip",
    "geo_anomaly",
    "combined_context",
]

ALL_ATTACK_FAMILIES = ATTACK_FAMILIES + P2_ATTACK_FAMILIES

FEATURE_COLUMNS = [
    "amount",
    "account_age_days",
    "transaction_count_1h",
    "transaction_count_24h",
    "avg_amount_30d",
    "amount_deviation",
    "device_age_days",
    "failed_auth_count",
    "merchant_risk",
    "distance_from_home",
    "country",
    "hour_of_day",
    "beneficiary_is_new",
    "destination_concentration",
    "merchant_count_24h",
]

# P2 context + network features. Never include labels or Red Team metadata.
FEATURE_COLUMNS_V020 = FEATURE_COLUMNS + [
    "geo_country_delta",
    "geo_impossible_travel",
    "geo_distance_delta",
    "device_account_count",
    "device_is_shared",
    "ip_account_count",
    "ip_is_shared",
    "beneficiary_fan_in",
    "beneficiary_txn_count",
    "beneficiary_customer_share",
    "network_degree",
    "mule_cluster_score",
]

LEAKAGE_COLUMNS = [
    "attack_family",
    "fraud_label",
    "simulation_id",
    "attack_id",
    "difficulty",
    "red_team_score",
    "ground_truth",
    "variant_id",
]


def ensure_dirs() -> None:
    for path in (PROCESSED_DIR, SYNTHETIC_DIR, MODELS_DIR, REPORTS_DIR, SIM_DIR, DATA_DIR):
        path.mkdir(parents=True, exist_ok=True)
