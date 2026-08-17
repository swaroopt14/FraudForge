"""Adversarial evaluation report — seed of the later closed loop."""

from __future__ import annotations

import json
from typing import Any

from app.core.config import REPORTS_DIR, ensure_dirs


FAMILY_COPY = {
    "account_takeover": {
        "finding": "New device, IP, and geo appear together with a spend jump.",
        "detected": ["new device", "failed auth count", "amount deviation"],
        "weak": ["session sequence", "shared-infrastructure graph"],
        "red": "Rotate devices more slowly and keep amounts nearer the baseline.",
        "blue": "Add login-to-pay latency and device-graph degree.",
    },
    "velocity_attack": {
        "finding": "Burst counts dominate the score; spacing is the tell.",
        "detected": ["transaction_count_1h", "merchant_count_24h"],
        "weak": ["inter-event time distribution"],
        "red": "Spread bursts across more hours.",
        "blue": "Add explicit inter-arrival features.",
    },
    "amount_anomaly": {
        "finding": "Amount versus personal baseline is highly separable.",
        "detected": ["amount_deviation", "amount"],
        "weak": ["merchant context for large purchases"],
        "red": "Split the spike across several tickets.",
        "blue": "Keep customer-level amount z-scores.",
    },
    "beneficiary_anomaly": {
        "finding": "A first-time destination with high concentration is visible.",
        "detected": ["beneficiary novelty", "destination concentration"],
        "weak": ["cumulative beneficiary graph"],
        "red": "Warm the destination with tiny prior pays.",
        "blue": "Add sequence + cumulative destination features.",
    },
    "low_and_slow": {
        "finding": "Individual transactions resemble legitimate customer behavior.",
        "detected": ["temporal deviation", "beneficiary novelty"],
        "weak": ["long-term sequence", "cumulative beneficiary concentration"],
        "red": "Increase behavioral mimicry.",
        "blue": "Add sequence + cumulative network features.",
    },
}


def render_report(
    run_id: str,
    attack_family: str,
    n: int,
    metrics: dict[str, Any],
    extra: dict[str, Any] | None = None,
) -> str:
    copy = FAMILY_COPY.get(attack_family, FAMILY_COPY["low_and_slow"])
    det = float(metrics.get("detection_rate") or metrics.get("recall") or 0.0)
    lines = [
        "================================================",
        f"ADVERSARIAL PAYMENT DEFENSE — RUN #{run_id}",
        "================================================",
        "",
        "Attack family:",
        attack_family.upper(),
        "",
        "Transactions:",
        str(int(n)),
        "",
        "Detection rate:",
        f"{det:.2%}",
        "",
        "Precision:",
        f"{float(metrics.get('precision') or 0):.2%}",
        "",
        "Recall:",
        f"{float(metrics.get('recall') or 0):.2%}",
        "",
        "F1:",
        f"{float(metrics.get('f1') or 0):.2%}",
        "",
        "PR-AUC:",
        f"{float(metrics.get('pr_auc') or 0):.2%}",
        "",
        "False-positive rate:",
        f"{float(metrics.get('fpr') or 0):.2%}",
        "",
        "High-value finding:",
        copy["finding"],
        "",
        "Detected signals:",
        *[f"- {s}" for s in copy["detected"]],
        "",
        "Weak signals:",
        *[f"- {s}" for s in copy["weak"]],
        "",
        "Red Team recommendation:",
        copy["red"],
        "",
        "Blue Team recommendation:",
        copy["blue"],
        "",
        "================================================",
    ]
    if extra:
        lines[0:0] = []
    text = "\n".join(lines) + "\n"
    ensure_dirs()
    (REPORTS_DIR / f"run_{run_id}.txt").write_text(text)
    (REPORTS_DIR / f"run_{run_id}.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "attack_family": attack_family,
                "transactions": int(n),
                "metrics": metrics,
                "report": text,
            },
            indent=2,
        )
    )
    return text
