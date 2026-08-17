"""Red Team attack report — computed metrics only."""

from __future__ import annotations

import json
from typing import Any

from app.core.config import REPORTS_DIR, ensure_dirs


def render_red_team_report(payload: dict[str, Any]) -> str:
    metrics = payload.get("metrics") or {}
    fidelity = payload.get("fidelity") or {}
    signals = payload.get("bypass_signals") or payload.get("detection_signals") or []
    finding = payload.get("finding") or "Computed from this run."
    det = float(metrics.get("detection_rate") or metrics.get("recall") or 0.0)
    success = 1.0 - det
    lines = [
        "==================================================",
        "RED TEAM ATTACK REPORT",
        "==================================================",
        "",
        "Simulation:",
        str(payload.get("simulation_id", "")),
        "",
        "Attack:",
        str(payload.get("attack_name") or payload.get("attack_id", "")),
        "",
        "Variant:",
        str(payload.get("variant_id", "")),
        "",
        "Intensity:",
        str(payload.get("difficulty", "")),
        "",
        "Transactions:",
        f"{int(payload.get('generated', 0)):,}",
        "",
        "Entities:",
        f"{int((payload.get('entities') or {}).get('entities', 0)):,}",
        "",
        "Attack Networks:",
        str(int((payload.get('entities') or {}).get('attack_networks', 0))),
        "",
        "--------------------------------------------------",
        "ATTACK RESULTS",
        "",
        f"Detection Rate:        {det:.1%}",
        f"Attack Success Rate:   {success:.1%}",
        "",
        f"Precision:             {float(metrics.get('precision') or 0):.1%}",
        f"Recall:                {float(metrics.get('recall') or 0):.1%}",
        f"F1:                    {float(metrics.get('f1') or 0):.1%}",
        f"False Positive Rate:    {float(metrics.get('fpr') or 0):.1%}",
        "",
        "--------------------------------------------------",
        "FIDELITY",
        "",
        f"Transaction Fidelity:  {float(fidelity.get('overall_fidelity') or 0):.2f}",
        f"Amount:                {float(fidelity.get('amount_distribution') or 0):.2f}",
        f"Temporal:              {float(fidelity.get('time_distribution') or 0):.2f}",
        f"Velocity:              {float(fidelity.get('velocity_distribution') or 0):.2f}",
        f"Merchant:              {float(fidelity.get('merchant_distribution') or 0):.2f}",
        f"Customer:              {float(fidelity.get('customer_behavior') or 0):.2f}",
        f"Sequence:              {float(fidelity.get('sequence_similarity') or 0):.2f}",
        f"Beneficiary:           {float(fidelity.get('beneficiary_behavior') or 0):.2f}",
        f"Network Fidelity:      {float(fidelity.get('network_fidelity') or 0):.2f}",
        "",
        "--------------------------------------------------",
        "PRIMARY BYPASS SIGNALS",
        "",
        *[f"• {s}" for s in (signals or ["none listed"])],
        "",
        "--------------------------------------------------",
        "RED TEAM FINDING",
        "",
        finding,
        "==================================================",
        "",
    ]
    text = "\n".join(lines)
    ensure_dirs()
    run_id = str(payload.get("simulation_id", "unknown"))
    (REPORTS_DIR / f"redteam_{run_id}.txt").write_text(text)
    (REPORTS_DIR / f"redteam_{run_id}.json").write_text(json.dumps({**payload, "report": text}, indent=2, default=str))
    return text
