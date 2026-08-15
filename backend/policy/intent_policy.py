"""Deterministic intent validation. Authoritative for destination / amount / category."""

from __future__ import annotations

from typing import Any


def evaluate_intent(intent: dict[str, Any], payment: dict[str, Any]) -> dict[str, Any]:
    reasons: list[str] = []
    amount = float(payment.get("amount") or 0)
    max_amount = float(intent.get("max_amount") or 0)
    destination = str(payment.get("destination") or "")
    approved = [str(x) for x in (intent.get("approved_destinations") or [])]
    category = str(payment.get("category") or "")
    allowed_cats = [str(x) for x in (intent.get("allowed_categories") or [])]

    if max_amount and amount > max_amount:
        reasons.append("amount_over_authorized_limit")
    if approved and destination and destination not in approved:
        reasons.append("destination_not_authorized")
        if payment.get("beneficiary_is_new"):
            reasons.append("beneficiary_is_new")
    if allowed_cats and category and category not in allowed_cats:
        reasons.append("category_outside_authorized_scope")
    if intent.get("expired"):
        reasons.append("intent_expired")

    score = 0.0
    if "destination_not_authorized" in reasons:
        score = max(score, 0.95)
    if "amount_over_authorized_limit" in reasons:
        score = max(score, 0.90)
    if "category_outside_authorized_scope" in reasons:
        score = max(score, 0.70)
    if "intent_expired" in reasons:
        score = max(score, 0.80)
    if "beneficiary_is_new" in reasons:
        score = max(score, 0.85)

    blocking = {
        "destination_not_authorized",
        "amount_over_authorized_limit",
        "intent_expired",
    }
    if reasons and set(reasons) & blocking:
        decision = "BLOCK"
    elif reasons:
        decision = "REVIEW"
    else:
        decision = "PASS"
        score = 0.05

    return {
        "score": round(score, 3),
        "decision": decision,
        "reason_codes": reasons,
        "violated": bool(reasons),
        "checks": {
            "amount_ok": "amount_over_authorized_limit" not in reasons,
            "destination_ok": "destination_not_authorized" not in reasons,
            "category_ok": "category_outside_authorized_scope" not in reasons,
            "intent_fresh": "intent_expired" not in reasons,
        },
    }
