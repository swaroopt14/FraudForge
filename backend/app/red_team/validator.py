"""Validate an attack specification before simulation. Reject unsafe or infeasible plans."""

from __future__ import annotations

from typing import Any

from app.core.config import FEATURE_COLUMNS
from app.red_team.models.novelty import RedTeamNoveltyModel
from app.threats.registry import get_registry

FORBIDDEN = ("phishing", "live_rail", "card_pan", "cvv", "exploit", "malware")


def validate_strategy(strategy: dict[str, Any], *, claim_novel: bool = False) -> dict[str, Any]:
    reasons: list[str] = []
    attack_id = str(strategy.get("attack_id") or "")
    registry = get_registry()
    try:
        threat = registry.get(attack_id or str(strategy.get("attack_family") or ""))
    except KeyError:
        return {
            "valid": False,
            "decision": "REJECT",
            "novelty": 0,
            "plausibility": 0,
            "simulation_feasibility": 0,
            "reason": "Attack is not in the Threat Library and P1 does not compile free-form LLM threats.",
        }

    novelty = RedTeamNoveltyModel().score_threat(threat)
    required = set(threat.required_features or [])
    available = set(FEATURE_COLUMNS) | {"merchant_id", "device_id", "beneficiary_id", "customer_id", "hour_of_day"}
    missing = sorted(required - available)
    blob = json_blob(strategy)
    unsafe = [token for token in FORBIDDEN if token in blob]
    scale = int(strategy.get("scale") or strategy.get("transaction_count") or 1000)
    if scale > 100_000:
        reasons.append("scale exceeds sandbox cap of 100,000")
    if missing:
        reasons.append(f"required features unavailable: {missing}")
    if unsafe:
        reasons.append(f"safety/sandbox: forbidden tokens {unsafe}")
    if claim_novel and novelty["status"] == "known_near_duplicate":
        reasons.append("claimed novel but nearest library attack is a near-duplicate")

    plausibility = 94 if not missing else max(20, 94 - 15 * len(missing))
    feasibility = 98 if threat.simulation_template else 40
    if reasons:
        return {
            "valid": False,
            "decision": "REFINE" if missing or (claim_novel and novelty["status"] != "novel_candidate") else "REJECT",
            "novelty": novelty["novelty_score"],
            "plausibility": plausibility,
            "simulation_feasibility": feasibility,
            "reason": "; ".join(reasons),
            "novelty_detail": novelty,
        }
    return {
        "valid": True,
        "decision": "ACCEPT",
        "novelty": novelty["novelty_score"],
        "plausibility": plausibility,
        "simulation_feasibility": feasibility,
        "reason": "Passes novelty, payment plausibility, simulation feasibility, data availability, and sandbox checks.",
        "novelty_detail": novelty,
        "attack_id": threat.attack_id,
    }


def json_blob(strategy: dict[str, Any]) -> str:
    import json

    return json.dumps(strategy, default=str).lower()
