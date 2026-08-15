"""Hypothesis-conditioned narrative features on top of the PCA credit-card table.

Judge scenarios need readable SHAP signals (new device, mule risk, constraint
violation) that the original V1–V28 columns do not provide. Legitimate rows
draw low-risk values; fraud rows and generated attacks draw from family
templates.
"""

from __future__ import annotations

from typing import Iterable

import numpy as np
import pandas as pd

from config import ATTACK_FAMILIES, HOLDOUT_FAMILY, NARRATIVE_FEATURES, RANDOM_STATE

# Ranges are (low, high) for continuous draws; ints are fixed flags.
FAMILY_TEMPLATES: dict[str, dict] = {
    "phishing_ato": {
        "device_new": 1,
        "velocity_1h": (5, 9),
        "location_mismatch": 1,
        "beneficiary_name_match": 1,
        "mule_account_risk": (0.15, 0.45),
        "constraint_violation": 0,
        "amount_vs_limit_ratio": (0.45, 0.95),
        "hour_of_day": (18.0, 23.5),
        "amount_range": (800.0, 3500.0),
    },
    "deepfake_upi": {
        "device_new": 0,
        "velocity_1h": (1, 3),
        "location_mismatch": 0,
        "beneficiary_name_match": 0,
        "mule_account_risk": (0.72, 0.98),
        "constraint_violation": 0,
        "amount_vs_limit_ratio": (0.18, 0.55),
        "hour_of_day": (7.0, 22.0),
        "amount_range": (180.0, 1400.0),
    },
    "malicious_agent": {
        "device_new": 0,
        "velocity_1h": (2, 6),
        "location_mismatch": 0,
        "beneficiary_name_match": 1,
        "mule_account_risk": (0.08, 0.28),
        "constraint_violation": 1,
        "amount_vs_limit_ratio": (1.15, 1.85),
        "hour_of_day": (9.0, 18.0),
        "amount_range": (1600.0, 4200.0),
    },
    "synthetic_identity": {
        "device_new": 1,
        "velocity_1h": (3, 7),
        "location_mismatch": 1,
        "beneficiary_name_match": 0,
        "mule_account_risk": (0.48, 0.88),
        "constraint_violation": 0,
        "amount_vs_limit_ratio": (0.55, 1.05),
        "hour_of_day": (10.0, 21.0),
        "amount_range": (400.0, 2400.0),
        "kyc_liveness_risk": (0.35, 0.70),
        "document_tamper_score": (0.62, 0.95),
        "biometric_mismatch": 0,
        "voiceprint_mismatch": 0,
    },
    "authorized_push": {
        "device_new": 0,
        "velocity_1h": (1, 4),
        "location_mismatch": 0,
        "beneficiary_name_match": 0,
        "mule_account_risk": (0.58, 0.94),
        "constraint_violation": 0,
        "amount_vs_limit_ratio": (0.28, 0.75),
        "hour_of_day": (8.0, 22.0),
        "amount_range": (350.0, 1900.0),
    },
    "qr_swap": {
        "device_new": 0,
        "velocity_1h": (1, 3),
        "location_mismatch": 1,
        "beneficiary_name_match": 0,
        "mule_account_risk": (0.65, 0.95),
        "constraint_violation": 0,
        "amount_vs_limit_ratio": (0.12, 0.48),
        "hour_of_day": (10.0, 21.0),
        "amount_range": (120.0, 900.0),
    },
    "sim_swap": {
        "device_new": 1,
        "velocity_1h": (4, 8),
        "location_mismatch": 1,
        "beneficiary_name_match": 1,
        "mule_account_risk": (0.22, 0.55),
        "constraint_violation": 0,
        "amount_vs_limit_ratio": (0.40, 0.90),
        "hour_of_day": (0.0, 6.5),
        "amount_range": (400.0, 2200.0),
    },
    "refund_llm": {
        "device_new": 0,
        "velocity_1h": (3, 6),
        "location_mismatch": 0,
        "beneficiary_name_match": 1,
        "mule_account_risk": (0.35, 0.70),
        "constraint_violation": 0,
        "amount_vs_limit_ratio": (0.20, 0.65),
        "hour_of_day": (9.0, 17.0),
        "amount_range": (80.0, 1600.0),
    },
    "prompt_injection_pay": {
        "device_new": 0,
        "velocity_1h": (2, 5),
        "location_mismatch": 0,
        "beneficiary_name_match": 0,
        "mule_account_risk": (0.40, 0.75),
        "constraint_violation": 1,
        "amount_vs_limit_ratio": (0.70, 1.25),
        "hour_of_day": (8.0, 20.0),
        "amount_range": (200.0, 1800.0),
    },
    "credential_stuffing": {
        "device_new": 1,
        "velocity_1h": (6, 12),
        "location_mismatch": 1,
        "beneficiary_name_match": 1,
        "mule_account_risk": (0.18, 0.50),
        "constraint_violation": 0,
        "amount_vs_limit_ratio": (0.15, 0.55),
        "hour_of_day": (1.0, 23.0),
        "amount_range": (15.0, 400.0),
    },
    "deepfake_kyc": {
        "device_new": 1,
        "velocity_1h": (2, 6),
        "location_mismatch": 1,
        "beneficiary_name_match": 1,
        "mule_account_risk": (0.55, 0.90),
        "constraint_violation": 0,
        "amount_vs_limit_ratio": (0.40, 0.95),
        "hour_of_day": (9.0, 20.0),
        "amount_range": (250.0, 1800.0),
        "kyc_liveness_risk": (0.72, 0.98),
        "document_tamper_score": (0.15, 0.45),
        "biometric_mismatch": 1,
        "voiceprint_mismatch": 0,
    },
    "document_forgery": {
        "device_new": 1,
        "velocity_1h": (2, 5),
        "location_mismatch": 0,
        "beneficiary_name_match": 0,
        "mule_account_risk": (0.42, 0.82),
        "constraint_violation": 0,
        "amount_vs_limit_ratio": (0.35, 0.88),
        "hour_of_day": (8.0, 18.0),
        "amount_range": (200.0, 1600.0),
        "kyc_liveness_risk": (0.08, 0.28),
        "document_tamper_score": (0.78, 0.99),
        "biometric_mismatch": 0,
        "voiceprint_mismatch": 0,
    },
    "face_swap": {
        "device_new": 1,
        "velocity_1h": (2, 6),
        "location_mismatch": 1,
        "beneficiary_name_match": 1,
        "mule_account_risk": (0.38, 0.75),
        "constraint_violation": 0,
        "amount_vs_limit_ratio": (0.30, 0.80),
        "hour_of_day": (9.0, 21.0),
        "amount_range": (180.0, 1500.0),
        "kyc_liveness_risk": (0.55, 0.88),
        "document_tamper_score": (0.10, 0.35),
        "biometric_mismatch": 1,
        "voiceprint_mismatch": 0,
    },
    "voice_clone_auth": {
        "device_new": 0,
        "velocity_1h": (4, 9),
        "location_mismatch": 1,
        "beneficiary_name_match": 1,
        "mule_account_risk": (0.12, 0.40),
        "constraint_violation": 0,
        "amount_vs_limit_ratio": (0.35, 0.90),
        "hour_of_day": (7.0, 22.0),
        "amount_range": (300.0, 2200.0),
        "kyc_liveness_risk": (0.04, 0.18),
        "document_tamper_score": (0.04, 0.18),
        "biometric_mismatch": 0,
        "voiceprint_mismatch": 1,
    },
    "voice_impersonation": {
        "device_new": 0,
        "velocity_1h": (1, 4),
        "location_mismatch": 0,
        "beneficiary_name_match": 0,
        "mule_account_risk": (0.62, 0.95),
        "constraint_violation": 0,
        "amount_vs_limit_ratio": (0.22, 0.70),
        "hour_of_day": (8.0, 22.0),
        "amount_range": (400.0, 2100.0),
        "kyc_liveness_risk": (0.04, 0.16),
        "document_tamper_score": (0.04, 0.16),
        "biometric_mismatch": 0,
        "voiceprint_mismatch": 1,
    },
    "deepfake_video": {
        "device_new": 0,
        "velocity_1h": (1, 3),
        "location_mismatch": 0,
        "beneficiary_name_match": 0,
        "mule_account_risk": (0.50, 0.88),
        "constraint_violation": 0,
        "amount_vs_limit_ratio": (0.20, 0.65),
        "hour_of_day": (9.0, 18.0),
        "amount_range": (250.0, 1400.0),
        "kyc_liveness_risk": (0.40, 0.75),
        "document_tamper_score": (0.08, 0.28),
        "biometric_mismatch": 1,
        "voiceprint_mismatch": 0,
    },
    "multilingual_scam": {
        "device_new": 0,
        "velocity_1h": (1, 4),
        "location_mismatch": 1,
        "beneficiary_name_match": 0,
        "mule_account_risk": (0.58, 0.94),
        "constraint_violation": 0,
        "amount_vs_limit_ratio": (0.25, 0.72),
        "hour_of_day": (6.0, 23.0),
        "amount_range": (200.0, 1700.0),
        "kyc_liveness_risk": (0.03, 0.14),
        "document_tamper_score": (0.03, 0.14),
        "biometric_mismatch": 0,
        "voiceprint_mismatch": 0,
    },
}

# All demo families appear in training so judge scenarios 1–3 are caught.
# Closed-loop novelty comes from adversarial washing, not a missing family.
TRAIN_FAMILY_WEIGHTS = {
    "phishing_ato": 0.18,
    "deepfake_upi": 0.12,
    "malicious_agent": 0.12,
    "synthetic_identity": 0.10,
    "authorized_push": 0.06,
    "deepfake_kyc": 0.08,
    "document_forgery": 0.08,
    "face_swap": 0.06,
    "voice_clone_auth": 0.06,
    "voice_impersonation": 0.06,
    "multilingual_scam": 0.06,
    "deepfake_video": 0.02,
}

FAMILY_TO_HYPOTHESIS = {
    "phishing_ato": "AI Phishing → Account Takeover",
    "deepfake_upi": "Deepfake Voice → UPI Collect Request",
    "malicious_agent": "Malicious AI Agent → Constraint Violation",
    "synthetic_identity": "Synthetic Identity → New Account Fraud",
    "authorized_push": "LLM Social Engineering → Authorized Push Payment",
    "qr_swap": "QR Code Swap → Payment Diversion",
    "sim_swap": "SIM Swap → OTP Theft → Debit",
    "refund_llm": "LLM Refund Claim → Merchant Loss",
    "prompt_injection_pay": "Prompt Injection → Agent Pays Attacker",
    "credential_stuffing": "Credential Stuffing → Account Takeover",
    "deepfake_kyc": "Deepfake KYC Bypass → New Account",
    "document_forgery": "Document Forgery → Identity Verification",
    "face_swap": "Face Swap → Video KYC",
    "voice_clone_auth": "Voice Cloning → Voice Biometric Login",
    "voice_impersonation": "Voice Cloning Impersonation → Payment Authorization",
    "deepfake_video": "Deepfake Video Call → Support Impersonation",
    "multilingual_scam": "Multilingual Scam Automation → Cross-Border APP",
}

_PCA_UNCHANGED = [f"V{i}" for i in range(1, 29)]

MUTATION_CONTRACTS: dict[str, dict[str, list[str]]] = {
    "phishing_ato": {
        "change": ["device_new", "location_mismatch", "hour_of_day", "velocity_1h", "Amount"],
        "keep_realistic": ["pca_correlations"],
        "keep_unchanged": ["seed_row", "Time_format", *_PCA_UNCHANGED],
    },
    "synthetic_identity": {
        "change": ["device_new", "location_mismatch", "mule_account_risk", "document_tamper_score"],
        "keep_realistic": ["amount_distribution"],
        "keep_unchanged": ["seed_row", "Time_format", *_PCA_UNCHANGED],
    },
    "malicious_agent": {
        "change": ["Amount", "amount_vs_limit_ratio", "constraint_violation"],
        "keep_realistic": ["user_seed"],
        "keep_unchanged": ["seed_row", "Time_format", *_PCA_UNCHANGED],
    },
    "intent_mismatch": {
        "change": ["Amount", "amount_vs_limit_ratio", "constraint_violation"],
        "keep_realistic": ["agent_user_seed"],
        "keep_unchanged": ["seed_row", "Time_format", *_PCA_UNCHANGED],
    },
    "deepfake_upi": {
        "change": ["beneficiary_name_match", "mule_account_risk", "Amount"],
        "keep_realistic": ["timestamp", "user_seed"],
        "keep_unchanged": ["seed_row", "Time_format", *_PCA_UNCHANGED],
    },
    "qr_swap": {
        "change": ["beneficiary_name_match", "location_mismatch", "mule_account_risk"],
        "keep_realistic": ["Amount", "timestamp"],
        "keep_unchanged": ["seed_row", "Time_format", *_PCA_UNCHANGED],
    },
    "authorized_push": {
        "change": ["beneficiary_name_match", "mule_account_risk", "Amount"],
        "keep_realistic": ["user_seed"],
        "keep_unchanged": ["seed_row", "Time_format", *_PCA_UNCHANGED],
    },
    "sim_swap": {
        "change": ["device_new", "location_mismatch", "hour_of_day", "velocity_1h"],
        "keep_realistic": ["pca_correlations"],
        "keep_unchanged": ["seed_row", "Time_format", *_PCA_UNCHANGED],
    },
    "refund_llm": {
        "change": ["velocity_1h", "mule_account_risk", "Amount"],
        "keep_realistic": ["user_seed"],
        "keep_unchanged": ["seed_row", "Time_format", *_PCA_UNCHANGED],
    },
    "prompt_injection_pay": {
        "change": ["beneficiary_name_match", "mule_account_risk", "constraint_violation", "Amount"],
        "keep_realistic": ["device_new", "user_seed"],
        "keep_unchanged": ["seed_row", "Time_format", *_PCA_UNCHANGED],
    },
    "credential_stuffing": {
        "change": ["device_new", "location_mismatch", "velocity_1h", "Amount"],
        "keep_realistic": ["pca_correlations"],
        "keep_unchanged": ["seed_row", "Time_format", *_PCA_UNCHANGED],
    },
    "deepfake_kyc": {
        "change": ["kyc_liveness_risk", "biometric_mismatch", "device_new", "mule_account_risk"],
        "keep_realistic": ["amount_distribution"],
        "keep_unchanged": ["seed_row", "Time_format", *_PCA_UNCHANGED],
    },
    "document_forgery": {
        "change": ["document_tamper_score", "device_new", "mule_account_risk"],
        "keep_realistic": ["amount_distribution"],
        "keep_unchanged": ["seed_row", "Time_format", *_PCA_UNCHANGED],
    },
    "face_swap": {
        "change": ["biometric_mismatch", "kyc_liveness_risk", "device_new"],
        "keep_realistic": ["user_seed"],
        "keep_unchanged": ["seed_row", "Time_format", *_PCA_UNCHANGED],
    },
    "voice_clone_auth": {
        "change": ["voiceprint_mismatch", "velocity_1h", "location_mismatch"],
        "keep_realistic": ["user_seed"],
        "keep_unchanged": ["seed_row", "Time_format", *_PCA_UNCHANGED],
    },
    "voice_impersonation": {
        "change": ["voiceprint_mismatch", "beneficiary_name_match", "mule_account_risk", "Amount"],
        "keep_realistic": ["timestamp", "user_seed"],
        "keep_unchanged": ["seed_row", "Time_format", *_PCA_UNCHANGED],
    },
    "deepfake_video": {
        "change": ["biometric_mismatch", "beneficiary_name_match", "mule_account_risk"],
        "keep_realistic": ["Amount", "timestamp"],
        "keep_unchanged": ["seed_row", "Time_format", *_PCA_UNCHANGED],
    },
    "multilingual_scam": {
        "change": ["location_mismatch", "beneficiary_name_match", "mule_account_risk", "Amount"],
        "keep_realistic": ["user_seed"],
        "keep_unchanged": ["seed_row", "Time_format", *_PCA_UNCHANGED],
    },
    "adaptive": {
        "change": ["Amount", "selected_v_and_overlay"],
        "keep_realistic": ["pca_correlations"],
        "keep_unchanged": ["seed_row", "Time"],
    },
}

GENERATABLE_FAMILIES = list(FAMILY_TEMPLATES.keys())


def _draw(template_value, rng: np.random.Generator, n: int) -> np.ndarray:
    if isinstance(template_value, tuple):
        lo, hi = template_value
        if isinstance(lo, int) and isinstance(hi, int):
            return rng.integers(lo, hi + 1, size=n)
        return rng.uniform(float(lo), float(hi), size=n)
    if isinstance(template_value, (int, np.integer)):
        return np.full(n, int(template_value), dtype=np.int64)
    return np.full(n, float(template_value), dtype=np.float64)


def overlay_legitimate(df: pd.DataFrame, rng: np.random.Generator | None = None) -> pd.DataFrame:
    """Low-risk behavioral overlay for non-fraud rows."""
    rng = rng or np.random.default_rng(RANDOM_STATE)
    n = len(df)
    amount = df["Amount"].to_numpy(dtype=float)
    limits = rng.uniform(1800.0, 8500.0, n)
    out = df.copy()
    out["device_new"] = rng.binomial(1, 0.035, n)
    out["velocity_1h"] = np.clip(rng.poisson(1.1, n), 0, 6)
    out["location_mismatch"] = rng.binomial(1, 0.025, n)
    out["beneficiary_name_match"] = rng.binomial(1, 0.975, n)
    out["mule_account_risk"] = np.clip(rng.beta(1.15, 14.0, n), 0.0, 1.0)
    out["constraint_violation"] = rng.binomial(1, 0.004, n)
    out["amount_vs_limit_ratio"] = np.clip(amount / limits, 0.01, 2.5)
    out["hour_of_day"] = (df["Time"].to_numpy(dtype=float) % 86400.0) / 3600.0
    out["kyc_liveness_risk"] = np.clip(rng.beta(1.1, 18.0, n), 0.0, 1.0)
    out["document_tamper_score"] = np.clip(rng.beta(1.1, 20.0, n), 0.0, 1.0)
    out["biometric_mismatch"] = rng.binomial(1, 0.008, n)
    out["voiceprint_mismatch"] = rng.binomial(1, 0.006, n)
    return out


def overlay_family(
    df: pd.DataFrame,
    family: str,
    rng: np.random.Generator | None = None,
    set_amount: bool = False,
    intensity: str = "medium",
) -> pd.DataFrame:
    """Apply one attack-family template to every row."""
    if family not in FAMILY_TEMPLATES:
        raise ValueError(f"Unknown attack family: {family}")
    rng = rng or np.random.default_rng(RANDOM_STATE)
    n = len(df)
    tmpl = FAMILY_TEMPLATES[family]
    out = df.copy()
    out["device_new"] = _draw(tmpl["device_new"], rng, n).astype(int)
    out["velocity_1h"] = _draw(tmpl["velocity_1h"], rng, n).astype(int)
    out["location_mismatch"] = _draw(tmpl["location_mismatch"], rng, n).astype(int)
    out["beneficiary_name_match"] = _draw(tmpl["beneficiary_name_match"], rng, n).astype(int)
    out["mule_account_risk"] = np.clip(_draw(tmpl["mule_account_risk"], rng, n), 0.0, 1.0)
    out["constraint_violation"] = _draw(tmpl["constraint_violation"], rng, n).astype(int)
    out["amount_vs_limit_ratio"] = _draw(tmpl["amount_vs_limit_ratio"], rng, n)
    out["hour_of_day"] = _draw(tmpl["hour_of_day"], rng, n)
    out["kyc_liveness_risk"] = np.clip(_draw(tmpl.get("kyc_liveness_risk", 0.02), rng, n), 0.0, 1.0)
    out["document_tamper_score"] = np.clip(_draw(tmpl.get("document_tamper_score", 0.02), rng, n), 0.0, 1.0)
    out["biometric_mismatch"] = _draw(tmpl.get("biometric_mismatch", 0), rng, n).astype(int)
    out["voiceprint_mismatch"] = _draw(tmpl.get("voiceprint_mismatch", 0), rng, n).astype(int)
    out["attack_family"] = family
    if set_amount:
        amounts = _draw(tmpl["amount_range"], rng, n)
        out["Amount"] = amounts
    level = (intensity or "medium").lower()
    if level == "low":
        seed_amt = pd.to_numeric(df.get("Amount"), errors="coerce").to_numpy(dtype=float)
        out["Amount"] = np.clip(seed_amt * 1.2, 1.0, None)
        if tmpl.get("device_new") != 1:
            out["device_new"] = 0
        out["velocity_1h"] = np.minimum(out["velocity_1h"].to_numpy(dtype=int), 3)
        out["hour_of_day"] = np.clip(out["hour_of_day"].to_numpy(dtype=float), 8.0, 20.0)
    elif level == "high":
        amt = tmpl.get("amount_range")
        if isinstance(amt, tuple):
            out["Amount"] = float(amt[1])
        vel = tmpl.get("velocity_1h")
        if isinstance(vel, tuple):
            out["velocity_1h"] = int(vel[1])
        hour = tmpl.get("hour_of_day")
        if isinstance(hour, tuple):
            out["hour_of_day"] = float(hour[0] if hour[0] < 6 else hour[1])
        if tmpl.get("device_new") == 1:
            out["device_new"] = 1
        if tmpl.get("location_mismatch") == 1:
            out["location_mismatch"] = 1
        if tmpl.get("biometric_mismatch") == 1:
            out["biometric_mismatch"] = 1
        if tmpl.get("voiceprint_mismatch") == 1:
            out["voiceprint_mismatch"] = 1
        for score_key in ("kyc_liveness_risk", "document_tamper_score"):
            val = tmpl.get(score_key)
            if isinstance(val, tuple):
                out[score_key] = float(val[1])
    out["mutation_intensity"] = level
    return out


def assign_train_families(n: int, rng: np.random.Generator) -> np.ndarray:
    names = list(TRAIN_FAMILY_WEIGHTS.keys())
    probs = np.array([TRAIN_FAMILY_WEIGHTS[k] for k in names], dtype=float)
    probs = probs / probs.sum()
    return rng.choice(names, size=n, p=probs)


def overlay_real_dataset(df: pd.DataFrame, seed: int = RANDOM_STATE) -> pd.DataFrame:
    """Add overlay columns. Fraud rows get in-distribution families only (no holdout family)."""
    rng = np.random.default_rng(seed)
    legit_mask = df["Class"] == 0
    fraud_mask = ~legit_mask

    legit = overlay_legitimate(df.loc[legit_mask], rng)
    fraud = df.loc[fraud_mask].copy()
    families = assign_train_families(len(fraud), rng)
    chunks = []
    for family in TRAIN_FAMILY_WEIGHTS:
        part = fraud.iloc[families == family]
        if part.empty:
            continue
        chunks.append(overlay_family(part, family, rng, set_amount=False))
    fraud_out = pd.concat(chunks, axis=0)

    out = pd.concat([legit, fraud_out], axis=0).sort_index()
    if "attack_family" not in out.columns:
        out["attack_family"] = "legitimate"
    out.loc[out["Class"] == 0, "attack_family"] = "legitimate"
    n_fraud = int((out["Class"] == 1).sum())
    n_synth = min(1500, max(80, n_fraud * 3))
    synth = _synthetic_family_attacks(out, n_total=n_synth, rng=rng)
    return pd.concat([out, synth], axis=0, ignore_index=True)


def _synthetic_family_attacks(
    df: pd.DataFrame,
    n_total: int = 1500,
    rng: np.random.Generator | None = None,
) -> pd.DataFrame:
    """Extra Class=1 rows: legitimate PCA seed + family overlay.

    Real ULB fraud already separates on V1–V28. Identity/auth families are
    learned from these overlays so the detector fires on KYC/auth flags too.
    """
    rng = rng or np.random.default_rng(RANDOM_STATE)
    legit = df.loc[df["Class"] == 0]
    if legit.empty or n_total <= 0:
        return df.iloc[0:0].copy()
    families = assign_train_families(n_total, rng)
    idx = rng.choice(len(legit), size=n_total, replace=True)
    seed = legit.iloc[idx].copy().reset_index(drop=True)
    attacks = apply_overlay_by_family(seed, families, rng, set_amount=True)
    attacks["Class"] = 1
    attacks["attack_source"] = "synthetic_overlay"
    return attacks


def apply_overlay_by_family(
    df: pd.DataFrame,
    families: Iterable[str],
    rng: np.random.Generator | None = None,
    set_amount: bool = True,
) -> pd.DataFrame:
    rng = rng or np.random.default_rng(RANDOM_STATE)
    families = list(families)
    if len(families) != len(df):
        raise ValueError("families length must match dataframe")
    parts = []
    work = df.copy()
    work["_family"] = families
    for family, part in work.groupby("_family", sort=False):
        parts.append(
            overlay_family(part.drop(columns=["_family"]), str(family), rng, set_amount=set_amount)
        )
    return pd.concat(parts, axis=0).sort_index()


def feature_matrix(df: pd.DataFrame) -> pd.DataFrame:
    from config import FEATURE_COLUMNS

    missing = [c for c in FEATURE_COLUMNS if c not in df.columns]
    if missing:
        raise KeyError(f"Missing feature columns: {missing}")
    return df[FEATURE_COLUMNS].astype(float)


def ensure_narrative(df: pd.DataFrame) -> pd.DataFrame:
    """Fill missing overlay and PCA columns so partial scenario rows still score."""
    from config import FEATURE_COLUMNS

    out = df.copy()
    if "Time" in out.columns:
        hour = (out["Time"].to_numpy(dtype=float) % 86400.0) / 3600.0
    else:
        hour = np.full(len(out), 12.0)
        out["Time"] = 0.0
    if "Amount" not in out.columns:
        out["Amount"] = 0.0
    defaults = {
        "device_new": 0,
        "velocity_1h": 1,
        "location_mismatch": 0,
        "beneficiary_name_match": 1,
        "mule_account_risk": 0.05,
        "constraint_violation": 0,
        "amount_vs_limit_ratio": 0.2,
        "hour_of_day": hour,
        "kyc_liveness_risk": 0.02,
        "document_tamper_score": 0.02,
        "biometric_mismatch": 0,
        "voiceprint_mismatch": 0,
    }
    for col, value in defaults.items():
        if col not in out.columns:
            out[col] = value
    for col in FEATURE_COLUMNS:
        if col not in out.columns:
            out[col] = 0.0
    return out


__all__ = [
    "ATTACK_FAMILIES",
    "FAMILY_TEMPLATES",
    "FAMILY_TO_HYPOTHESIS",
    "MUTATION_CONTRACTS",
    "HOLDOUT_FAMILY",
    "NARRATIVE_FEATURES",
    "apply_overlay_by_family",
    "assign_train_families",
    "ensure_narrative",
    "feature_matrix",
    "overlay_family",
    "overlay_legitimate",
    "overlay_real_dataset",
    "GENERATABLE_FAMILIES",
    "TRAIN_FAMILY_WEIGHTS",
]
