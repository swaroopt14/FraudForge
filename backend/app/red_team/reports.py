"""Red feedback extracted from a Blue defense report."""

from __future__ import annotations

from typing import Any


def red_feedback_from_blue(blue_report: dict[str, Any]) -> dict[str, Any]:
    det = float(blue_report.get("detection_rate") or 0.0)
    return {
        "simulation_id": blue_report.get("simulation_id"),
        "attack_detected": det,
        "missed": 1.0 - det,
        "weak_signals": blue_report.get("weak_signals") or [],
        "strong_signals": blue_report.get("top_detection_signals") or [],
        "model_version": blue_report.get("model_version"),
        "classification": blue_report.get("attack_classification"),
        "time_to_detect_ms": blue_report.get("time_to_detect_ms"),
        "use": "choose the next attack strategy; do not copy Blue features into Red training labels as Blue inputs",
    }
