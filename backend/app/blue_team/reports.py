"""Blue defense report from a scored simulation."""

from __future__ import annotations

import json
from collections import Counter
from typing import Any

from app.core.config import FEATURE_VERSION, REPORTS_DIR, ensure_dirs
from app.blue_team.knowledge import load_entry


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


def blue_feedback_from_red(red_result: dict[str, Any]) -> dict[str, Any]:
    return {
        "simulation_id": red_result.get("simulation_id"),
        "attack_id": red_result.get("attack_id"),
        "missed_transactions": red_result.get("missed_transactions") or [],
        "false_positives": [],
        "attack_distributions": {
            "generated": red_result.get("generated"),
            "detected": red_result.get("detected"),
            "missed": red_result.get("missed"),
            "fidelity": (red_result.get("fidelity") or {}).get("overall_fidelity"),
        },
        "use": "hard negatives and feature candidates for a future BLUE version; never train on attack_id",
    }


def build_defense_report(
    result: dict[str, Any],
    *,
    identifications: list[dict[str, Any]] | None = None,
    timings: dict[str, Any] | None = None,
) -> dict[str, Any]:
    metrics = result.get("metrics") or {}
    identifications = identifications or []
    families = Counter(row.get("family") for row in identifications if row.get("family"))
    top_family, top_n = (families.most_common(1)[0] if families else (None, 0))
    del top_n
    conf = 0.0
    if identifications:
        conf = float(sum(float(r.get("confidence") or 0) for r in identifications) / max(len(identifications), 1))
    try:
        kb = load_entry(str(result.get("attack_id") or ""))
        signals = kb.get("observable_signals") or result.get("detection_signals") or []
    except Exception:
        signals = result.get("detection_signals") or []
    timings = timings or {}
    report = {
        "simulation_id": result.get("simulation_id"),
        "attack_family": result.get("attack_family") or result.get("attack_id"),
        "attack_variant": result.get("variant_id"),
        "attack_start_time": timings.get("attack_start"),
        "attack_end_time": timings.get("attack_end"),
        "transactions_generated": result.get("generated"),
        "transactions_scored": result.get("generated"),
        "detected": result.get("detected"),
        "missed": result.get("missed"),
        "detection_rate": result.get("detection_rate"),
        "precision": metrics.get("precision"),
        "recall": metrics.get("recall"),
        "f1": metrics.get("f1"),
        "pr_auc": metrics.get("pr_auc"),
        "roc_auc": metrics.get("roc_auc"),
        "false_positive_rate": metrics.get("fpr"),
        "first_detection_time": timings.get("first_detection"),
        "time_to_detect_ms": timings.get("time_to_detect_ms"),
        "time_to_classify_ms": timings.get("time_to_classify_ms"),
        "time_to_mitigate_ms": timings.get("time_to_mitigate_ms"),
        "attack_classification": top_family or "UNKNOWN",
        "classification_confidence": conf,
        "top_detection_signals": signals[:6],
        "weak_signals": result.get("bypass_signals") or signals,
        "missing_signals": [],
        "mitigation_actions": ["ALLOW", "STEP_UP", "REVIEW", "BLOCK"],
        "mitigation_success": float(result.get("detection_rate") or 0.0),
        "false_positives": metrics.get("fpr"),
        "model_version": result.get("model_version"),
        "feature_version": FEATURE_VERSION,
        "timings": timings,
    }
    if (result.get("attack_id") or "").startswith("MUL") or "mule" in str(result.get("attack_family") or "").lower():
        report["missing_signals"] = ["beneficiary_fan_in_24h", "shared_device_count"]
        report["note"] = "Mule fan-in is not a BLUE-0.1.0 feature. Network risk is P2."
    if (result.get("attack_id") or "").startswith("BEN"):
        report["note"] = "beneficiary_is_new is present but non-discriminative on IEEE. Honest miss."
    return report


def persist_defense_report(report: dict[str, Any]) -> str:
    ensure_dirs()
    sid = str(report.get("simulation_id") or "unknown")
    path = REPORTS_DIR / f"blueteam_{sid}.json"
    path.write_text(json.dumps(report, indent=2, default=str))
    return str(path)
