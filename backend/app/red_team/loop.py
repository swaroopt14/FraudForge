"""Attach Blue report, Red feedback, and memories to a finished simulation."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from app.blue_team.memory import record_misses
from app.blue_team.classifiers.attack_classifier import BlueAttackClassifier
from app.blue_team.reports import blue_feedback_from_red, build_defense_report, persist_defense_report
from app.blue_team.risk import combine
from app.red_team.memory import record as record_red
from app.red_team.models.novelty import RedTeamNoveltyModel
from app.red_team.reports import red_feedback_from_blue
from app.threats.registry import get_registry


def enrich_run(
    result: dict[str, Any],
    rows: pd.DataFrame,
    proba: np.ndarray,
    *,
    timings: dict[str, Any],
    classifier: BlueAttackClassifier | None = None,
) -> dict[str, Any]:
    clf = classifier or BlueAttackClassifier.load()
    ident = clf.predict(rows, proba)
    preview = result.get("preview") or []
    for i, rec in enumerate(preview):
        if i < len(ident):
            rec["attack_identification"] = ident[i]
            rec["risk"] = combine(float(rec.get("fraud_probability") or 0.0))
    missed = result.get("missed_transactions") or []
    for rec in missed:
        rec["risk"] = combine(float(rec.get("fraud_probability") or 0.0))
    try:
        threat = get_registry().get(str(result.get("attack_id") or ""))
        mutation = (result.get("contract") or {}).get("mutation")
        result["novelty"] = RedTeamNoveltyModel().score_threat(threat, mutation)
    except Exception:
        result["novelty"] = {"novelty_score": 0, "status": "unknown"}
    blue_report = build_defense_report(result, identifications=ident, timings=timings)
    persist_defense_report(blue_report)
    result["blue_report"] = blue_report
    result["red_feedback"] = red_feedback_from_blue(blue_report)
    result["blue_feedback"] = blue_feedback_from_red(result)
    record_red(
        {
            "simulation_id": result.get("simulation_id"),
            "attack_id": result.get("attack_id"),
            "blue_feedback": result["red_feedback"],
            "novelty": result.get("novelty"),
        }
    )
    record_misses(str(result.get("simulation_id")), missed, str(result.get("model_version") or ""))
    return result
