"""In-memory Blue Team operational store for the latest scored stream."""

from __future__ import annotations

from typing import Any

import pandas as pd

_STATE: dict[str, Any] = {
    "simulation_id": None,
    "attack_family": None,
    "variant_id": None,
    "model_id": None,
    "started_at": None,
    "detections": [],
    "frame": None,
    "mitigations": {},
    "report": None,
    "metrics": None,
    "coverage": None,
    "p0_metrics": None,
    "p2_metrics": None,
    "timing": None,
}


def clear() -> None:
    _STATE["simulation_id"] = None
    _STATE["detections"] = []
    _STATE["frame"] = None
    _STATE["mitigations"] = {}
    _STATE["report"] = None
    _STATE["metrics"] = None
    _STATE["coverage"] = None
    _STATE["timing"] = None


def put_stream(**kwargs: Any) -> None:
    _STATE.update(kwargs)


def get_state() -> dict[str, Any]:
    return _STATE


def frame() -> pd.DataFrame:
    f = _STATE.get("frame")
    if f is None:
        return pd.DataFrame()
    return f


def detections() -> list[dict[str, Any]]:
    return list(_STATE.get("detections") or [])


def apply_mitigation(transaction_id: str, action: str, reason: str) -> dict[str, Any]:
    rec = {"transaction_id": transaction_id, "action": action, "reason": reason, "found": False}
    _STATE["mitigations"][transaction_id] = rec
    for row in _STATE.get("detections") or []:
        if str(row.get("transaction_id")) == str(transaction_id):
            row["action"] = action
            row["decision"] = action
            row["mitigation_reason"] = reason
            rec["found"] = True
            rec["risk_score"] = row.get("risk_score")
    return rec
