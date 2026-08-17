from __future__ import annotations

import numpy as np
import pandas as pd

from app.core.config import FEATURE_COLUMNS, LEAKAGE_FORBIDDEN
from app.redteam.agents import attach_agent_intent
from app.redteam.difficulty import LEVELS, adaptive_mutation, lerp_mutation
from app.redteam.graph import build_edge_table, edge_fingerprint, graph_payload
from app.threats.registry import get_registry
from app.threats.schema import MutationParams


def _rows(n: int = 24) -> pd.DataFrame:
    rng = np.random.default_rng(0)
    return pd.DataFrame(
        {
            "transaction_id": [f"t-{i}" for i in range(n)],
            "customer_id": [f"c-{i % 6}" for i in range(n)],
            "device_id": [f"d-{i % 3}" for i in range(n)],
            "ip_id": [f"ip-{i % 4}" for i in range(n)],
            "merchant_id": [f"m-{i % 5}" for i in range(n)],
            "beneficiary_id": [f"b-{i % 2}" for i in range(n)],
            "amount": rng.uniform(10, 120, n),
            "hour_of_day": rng.uniform(0, 23, n),
            "amount_deviation": rng.uniform(0, 1, n),
            "merchant_category": ["W"] * n,
        }
    )


def test_edge_table_and_fingerprint() -> None:
    edges = build_edge_table(_rows())
    assert edges
    assert {e["relation"] for e in edges} <= {
        "uses_device",
        "uses_ip",
        "pays_merchant",
        "pays_beneficiary",
        "connected_from",
        "located_in",
    }
    graph = graph_payload(_rows(), family="mule_network", attack_id="MUL-001")
    assert graph["n_edges"] == len(edges)
    assert graph["nodes"]
    assert graph["focus"]["nodes"]
    assert graph["stats"]["n_nodes"] >= graph["focus"]["n_nodes"]
    assert graph["path"]
    assert edge_fingerprint(edges) == edge_fingerprint(build_edge_table(_rows()))


def test_agent_and_intent_events() -> None:
    rng = np.random.default_rng(7)
    agt, agt_events = attach_agent_intent(_rows(), "agent_scope", rng)
    assert agt_events
    assert (agt["agent_id"] != "").all()
    intent, intent_events = attach_agent_intent(_rows(), "intent_mismatch", np.random.default_rng(7))
    assert intent_events
    assert (intent["intent_id"] != "").all()
    other, other_events = attach_agent_intent(_rows(), "account_takeover", np.random.default_rng(7))
    assert other_events == []
    assert "agent_id" not in FEATURE_COLUMNS
    assert "intent_id" not in FEATURE_COLUMNS
    assert "agent_id" in LEAKAGE_FORBIDDEN


def test_adaptive_lerp_is_between_low_and_high() -> None:
    assert "ADAPTIVE" in LEVELS
    registry = get_registry()
    low = registry.mutation("ATO-001", "LOW")
    high = registry.mutation("ATO-001", "HIGH")
    mid = lerp_mutation(low, high, 0.5)
    adapted = adaptive_mutation(registry, "ATO-001", None, 0.8)
    assert min(low.amount_deviation, high.amount_deviation) <= mid.amount_deviation <= max(
        low.amount_deviation, high.amount_deviation
    )
    assert isinstance(adapted, MutationParams)
    a = adaptive_mutation(registry, "ATO-001", None, 0.4)
    b = adaptive_mutation(registry, "ATO-001", None, 0.4)
    assert a.model_dump() == b.model_dump()
