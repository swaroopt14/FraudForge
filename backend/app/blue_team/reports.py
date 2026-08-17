"""Blue defense report from a scored simulation."""

from __future__ import annotations

from typing import Any


def render_defense_report(payload: dict[str, Any]) -> str:
    m = payload.get("metrics") or {}
    ident = payload.get("identification") or {}
    timing = payload.get("timing") or {}
    mit = payload.get("mitigation") or {}
    gap = payload.get("gap") or {}
    lines = [
        "BLUE DEFENSE REPORT",
        "──────────────────────────────────",
        "",
        f"Simulation: {payload.get('simulation_id', '—')}",
        f"Attack: {payload.get('attack_family', '—')}",
        f"Variant: {payload.get('variant_id', '—')}",
        f"Model: {payload.get('model_id', 'BLUE-FRAUD-0.2.0')}",
        "",
        f"Transactions: {payload.get('transactions', 0)}",
        "",
        "DETECTION",
        f"Detected             {payload.get('detected', 0)}",
        f"Missed               {payload.get('missed', 0)}",
        f"Precision             {float(m.get('precision') or 0):.1%}",
        f"Recall                {float(m.get('recall') or 0):.1%}",
        f"F1                    {float(m.get('f1') or 0):.1%}",
        f"PR-AUC                {float(m.get('pr_auc') or 0):.1%}",
        f"FPR                    {float(m.get('fpr') or 0):.1%}",
        "",
        "IDENTIFICATION",
    ]
    for fam, share in ident.items():
        lines.append(f"{fam:<22} {float(share):.0%}")
    lines += [
        "",
        "TIMING",
        f"Time to detect        {timing.get('time_to_detect_s', '—')} sec",
        f"Time to classify      {timing.get('time_to_classify_s', '—')} sec",
        f"Time to mitigate      {timing.get('time_to_mitigate_s', '—')} sec",
        "",
        "MITIGATION",
        f"Blocked               {mit.get('BLOCK', 0)}",
        f"Held                  {mit.get('HOLD', 0)}",
        f"Reviewed              {mit.get('REVIEW', 0)}",
        f"Step-up               {mit.get('STEP_UP', 0)}",
        f"Allow                 {mit.get('ALLOW', 0)}",
        "",
        "MISSED ATTACKS",
        str(payload.get("missed", 0)),
        "",
        f"Primary gap: {gap.get('primary', '—')}",
        f"Recommended: {gap.get('recommended', '—')}",
        "",
    ]
    return "\n".join(lines)
