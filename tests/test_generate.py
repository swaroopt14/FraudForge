"""Generate overlay mutation contracts."""

from __future__ import annotations

import numpy as np
import pandas as pd

from features import MUTATION_CONTRACTS, overlay_family, overlay_legitimate


def _seed(n: int = 8) -> pd.DataFrame:
    return pd.DataFrame(
        [{**{f"V{i}": 0.0 for i in range(1, 29)}, "Time": 1000.0, "Amount": 200.0, "Class": 0}] * n
    )


def test_mutation_contract_exists_for_flagship_family() -> None:
    assert "prompt_injection_pay" in MUTATION_CONTRACTS
    change = MUTATION_CONTRACTS["prompt_injection_pay"]["change"]
    assert "beneficiary_name_match" in change
    assert "constraint_violation" in change


def test_overlay_prompt_injection_sets_intent_flags() -> None:
    seed = _seed()
    legit = overlay_legitimate(seed, rng=np.random.default_rng(42))
    mutated = overlay_family(
        seed, "prompt_injection_pay", rng=np.random.default_rng(42), set_amount=True, intensity="medium"
    )
    assert int(mutated["constraint_violation"].iloc[0]) == 1
    assert int(mutated["beneficiary_name_match"].iloc[0]) == 0
    assert float(legit["constraint_violation"].mean()) < 0.05


def test_identity_auth_overlays_are_distinct() -> None:
    seed = _seed(n=4)
    kyc = overlay_family(seed, "deepfake_kyc", rng=np.random.default_rng(0))
    docs = overlay_family(seed, "document_forgery", rng=np.random.default_rng(0))
    voice = overlay_family(seed, "voice_clone_auth", rng=np.random.default_rng(0))
    assert int(kyc["biometric_mismatch"].iloc[0]) == 1
    assert float(kyc["kyc_liveness_risk"].iloc[0]) > 0.7
    assert float(docs["document_tamper_score"].iloc[0]) > 0.7
    assert int(docs["biometric_mismatch"].iloc[0]) == 0
    assert int(voice["voiceprint_mismatch"].iloc[0]) == 1
    from attack_catalog import IDENTITY_AUTH_FAMILY_IDS
    from features import FAMILY_TEMPLATES, TRAIN_FAMILY_WEIGHTS

    for fid in IDENTITY_AUTH_FAMILY_IDS:
        assert fid in FAMILY_TEMPLATES
        assert fid in TRAIN_FAMILY_WEIGHTS
