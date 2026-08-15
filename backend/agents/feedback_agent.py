"""Turn bypassed vs detected attacks into new defensive hypotheses."""

from __future__ import annotations

import json
from typing import Any

import numpy as np
import pandas as pd

from config import FEATURE_COLUMNS
from features import FAMILY_TO_HYPOTHESIS


FALLBACK_NEW = [
    {
        "attack_name": "Constraint-blend ATO",
        "attack_vector": "Account takeover that stays under velocity caps while exceeding delegated spend",
        "evasion_strategy": "Keep velocity_1h low and device_new=0 while amount_vs_limit_ratio > 1",
        "detectable_signals": ["constraint_violation", "amount_vs_limit_ratio", "mule_account_risk"],
        "attack_family": "malicious_agent",
    },
    {
        "attack_name": "Mule drip after deepfake collect",
        "attack_vector": "Small repeated collect-style debits to a mule beneficiary",
        "evasion_strategy": "Split Amount below typical fraud bands; keep beneficiary_name_match=0",
        "detectable_signals": ["mule_account_risk", "beneficiary_name_match", "velocity_1h"],
        "attack_family": "deepfake_upi",
    },
    {
        "attack_name": "Synthetic identity warm-up",
        "attack_vector": "New-device identity with gradual limit testing before a high-value hit",
        "evasion_strategy": "Start with legitimate-like mule_account_risk then spike Amount",
        "detectable_signals": ["device_new", "location_mismatch", "amount_vs_limit_ratio"],
        "attack_family": "synthetic_identity",
    },
]


class FeedbackAgent:
    def __init__(self, llm: Any | None = None) -> None:
        self.llm = llm

    def analyze_failures(
        self,
        bypassed_attacks: pd.DataFrame | np.ndarray,
        detected_attacks: pd.DataFrame | np.ndarray,
    ) -> str:
        bypassed = _as_frame(bypassed_attacks)
        detected = _as_frame(detected_attacks)
        if bypassed.empty or detected.empty:
            return (
                f"Failure analysis: {len(bypassed)} bypassed, {len(detected)} detected. "
                "Not enough of both classes to compare feature means."
            )
        diff = bypassed.mean(numeric_only=True) - detected.mean(numeric_only=True)
        top = diff.abs().sort_values(ascending=False).head(5)
        lines = [
            "Failure analysis:",
            f"- {len(bypassed)} attacks bypassed detection",
            f"- {len(detected)} attacks were caught",
            f"- Largest mean gaps (bypassed − detected): {', '.join(top.index.tolist())}",
        ]
        for feat, val in top.items():
            lines.append(f"  {feat}: {val:+.4f}")
        return "\n".join(lines)

    def generate_new_hypotheses(
        self,
        failure_analysis: str,
        attack_history: list | None = None,
    ) -> list[dict[str, Any]]:
        attack_history = attack_history or list(FAMILY_TO_HYPOTHESIS.values())
        if self.llm is None:
            return list(FALLBACK_NEW)
        prompt = f"""You are a payment-fraud blue-team analyst. Based on this failure analysis,
propose 3 NEW attack hypotheses a red team might try next. Defensive summaries only —
no phishing copy, malware, or exploit steps.

Failure analysis:
{failure_analysis}

Previous attack history:
{attack_history}

Return JSON array of 3 objects with keys:
attack_name, attack_vector, evasion_strategy, detectable_signals (array of feature names),
attack_family (one of phishing_ato, deepfake_upi, malicious_agent, synthetic_identity, authorized_push).
"""
        try:
            if hasattr(self.llm, "chat"):
                resp = self.llm.chat.completions.create(
                    model="gpt-4o",
                    temperature=0.4,
                    response_format={"type": "json_object"},
                    messages=[
                        {"role": "system", "content": 'Return JSON {"hypotheses": [...]} only.'},
                        {"role": "user", "content": prompt},
                    ],
                )
                parsed = json.loads(resp.choices[0].message.content or "{}")
                data = parsed.get("hypotheses", parsed) if isinstance(parsed, dict) else parsed
            else:
                response = self.llm.invoke(prompt)
                text = response.content if hasattr(response, "content") else str(response)
                data = json.loads(text)
            if isinstance(data, list) and data:
                return data
        except Exception:  # noqa: BLE001
            pass
        return list(FALLBACK_NEW)


def _as_frame(data: pd.DataFrame | np.ndarray) -> pd.DataFrame:
    if isinstance(data, pd.DataFrame):
        return data
    arr = np.asarray(data)
    if arr.ndim == 1:
        arr = arr.reshape(1, -1)
    cols = FEATURE_COLUMNS[: arr.shape[1]]
    return pd.DataFrame(arr, columns=cols)


__all__ = ["FeedbackAgent"]
