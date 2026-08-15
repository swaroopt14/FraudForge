"""Lightweight adversarial perturber — evade the detector while keeping amount high.

DQN + Box actions from the original spec is invalid (DQN is discrete). This
optimizer does evolutionary random search on Amount, PCA features, and narrative
risk flags so the closed-loop demo does not depend on live RL training.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from config import FEATURE_COLUMNS, RANDOM_STATE
from features import ensure_narrative, feature_matrix


NARRATIVE_TOWARD_LEGIT = {
    "device_new": 0.0,
    "velocity_1h": 1.0,
    "location_mismatch": 0.0,
    "beneficiary_name_match": 1.0,
    "mule_account_risk": 0.08,
    "constraint_violation": 0.0,
    "amount_vs_limit_ratio": 0.25,
}


class AdversarialOptimizer:
    def __init__(self, detector, n_iters: int = 24, seed: int = RANDOM_STATE) -> None:
        self.detector = detector
        self.n_iters = n_iters
        self.rng = np.random.default_rng(seed)

    def generate_adversarial_attacks(
        self,
        synthetic_fraud: pd.DataFrame,
        n_attacks: int | None = None,
    ) -> pd.DataFrame:
        frame = ensure_narrative(synthetic_fraud)
        if n_attacks is not None:
            frame = frame.iloc[:n_attacks].copy()
        else:
            frame = frame.copy()

        X = feature_matrix(frame).to_numpy(dtype=float)
        names = list(FEATURE_COLUMNS)
        name_idx = {n: i for i, n in enumerate(names)}
        best = X.copy()
        best_scores = self.detector.predict(pd.DataFrame(best, columns=names))

        v_idx = [i for i, n in enumerate(names) if n.startswith("V")]
        amount_i = name_idx["Amount"]

        for _ in range(self.n_iters):
            cand = best.copy()
            cand[:, v_idx] *= 1.0 + self.rng.uniform(-0.10, 0.10, size=(len(cand), len(v_idx)))
            cand[:, amount_i] *= 1.0 + self.rng.uniform(-0.05, 0.12, size=len(cand))
            cand[:, amount_i] = np.clip(cand[:, amount_i], 0.01, None)

            for feat, target in NARRATIVE_TOWARD_LEGIT.items():
                if feat not in name_idx:
                    continue
                i = name_idx[feat]
                blend = self.rng.uniform(0.35, 0.85, size=len(cand))
                cand[:, i] = cand[:, i] * (1.0 - blend) + target * blend
                if feat in {
                    "device_new",
                    "location_mismatch",
                    "beneficiary_name_match",
                    "constraint_violation",
                }:
                    cand[:, i] = (cand[:, i] >= 0.5).astype(float)

            scores = self.detector.predict(pd.DataFrame(cand, columns=names))
            amounts = cand[:, amount_i]
            # Prefer evasion; break ties with higher amount.
            improved = (scores < best_scores - 1e-4) | (
                (np.abs(scores - best_scores) < 1e-4) & (amounts > best[:, amount_i])
            )
            best[improved] = cand[improved]
            best_scores[improved] = scores[improved]

        out = frame.copy()
        out[names] = best
        out["adv_score"] = best_scores
        return out


__all__ = ["AdversarialOptimizer"]
