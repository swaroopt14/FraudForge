"""Probability → ALLOW / STEP_UP / REVIEW / BLOCK."""

from __future__ import annotations

from app.core.config import ALLOW_THRESHOLD, REVIEW_THRESHOLD, STEP_UP_THRESHOLD


def decide(
    probability: float,
    allow: float | None = None,
    step_up: float | None = None,
    review: float | None = None,
) -> str:
    p = float(probability)
    a = ALLOW_THRESHOLD if allow is None else allow
    s = STEP_UP_THRESHOLD if step_up is None else step_up
    r = REVIEW_THRESHOLD if review is None else review
    if p < a:
        return "ALLOW"
    if p < s:
        return "STEP_UP"
    if p < r:
        return "REVIEW"
    return "BLOCK"
