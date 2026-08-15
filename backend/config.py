"""Paths, feature names, and runtime defaults."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent
ROOT_DIR = BACKEND_DIR.parent
DATA_DIR = BACKEND_DIR / "data"
CREDITCARD_DIR = DATA_DIR / "creditcard"
CREDITCARD_PATH = CREDITCARD_DIR / "creditcard.csv"
MODELS_DIR = BACKEND_DIR / "models"
DEMO_DIR = DATA_DIR / "demo"
DB_PATH = DATA_DIR / "fraudforge.db"

load_dotenv(ROOT_DIR / ".env")

PCA_FEATURES = ["Time"] + [f"V{i}" for i in range(1, 29)] + ["Amount"]
NARRATIVE_FEATURES = [
    "device_new",
    "velocity_1h",
    "location_mismatch",
    "beneficiary_name_match",
    "mule_account_risk",
    "constraint_violation",
    "amount_vs_limit_ratio",
    "hour_of_day",
    "kyc_liveness_risk",
    "document_tamper_score",
    "biometric_mismatch",
    "voiceprint_mismatch",
]
LABEL_COL = "Class"
FEATURE_COLUMNS = PCA_FEATURES + NARRATIVE_FEATURES

DETECTOR_PATH = MODELS_DIR / "detector.pkl"
CTGAN_PATH = MODELS_DIR / "ctgan.pkl"
AUTOENCODER_PATH = MODELS_DIR / "autoencoder.pt"
SCENARIOS_PATH = DEMO_DIR / "scenarios.json"
CLOSED_LOOP_PATH = DEMO_DIR / "closed_loop.json"
THREAT_INTEL_PATH = DEMO_DIR / "threat_intel.json"

RANDOM_STATE = 42
CTGAN_EPOCHS = int(os.getenv("FRAUDFORGE_CTGAN_EPOCHS", "50"))
AE_EPOCHS = int(os.getenv("FRAUDFORGE_AE_EPOCHS", "20"))
AE_SUBSAMPLE = int(os.getenv("FRAUDFORGE_AE_SUBSAMPLE", "50000"))
API_URL = os.getenv("FRAUDFORGE_API_URL", "http://127.0.0.1:8000")

# Hold this family out of the initial detector so closed-loop novelty is visible.
HOLDOUT_FAMILY = "malicious_agent"

ATTACK_FAMILIES = [
    "phishing_ato",
    "deepfake_upi",
    "malicious_agent",
    "synthetic_identity",
    "authorized_push",
]
