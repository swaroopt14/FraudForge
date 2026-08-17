"""Deterministic agent / intent events. Not LLM transaction generation."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

TOOLS = ("pay", "transfer", "schedule")


def attach_agent_intent(df: pd.DataFrame, family: str, rng: np.random.Generator) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    out = df.copy()
    n = len(out)
    out["agent_id"] = ""
    out["intent_id"] = ""
    out["agent_in_scope"] = 1.0
    out["intent_match"] = 1.0
    events: list[dict[str, Any]] = []
    if n == 0 or family not in {"agent_scope", "intent_mismatch"}:
        return out, events

    if family == "agent_scope":
        n_agents = max(1, min(12, n // 8 or 1))
        agents = []
        for i in range(n_agents):
            agents.append(
                {
                    "agent_id": f"agent-{int(rng.integers(1000, 9999))}-{i}",
                    "tool": TOOLS[int(rng.integers(0, len(TOOLS)))],
                    "max_amount": float(rng.uniform(20.0, 80.0)),
                    "hour_lo": 8.0,
                    "hour_hi": 18.0,
                }
            )
        out = out.reset_index(drop=True)
        for i, row in out.iterrows():
            agent = agents[int(i) % n_agents]
            hour = float(row.get("hour_of_day", 12.0))
            amount = float(row.get("amount", 0.0))
            in_scope = bool(agent["hour_lo"] <= hour <= agent["hour_hi"] and amount <= agent["max_amount"])
            out.at[i, "agent_id"] = agent["agent_id"]
            out.at[i, "agent_in_scope"] = 1.0 if in_scope else 0.0
            reason = "in_scope"
            if amount > agent["max_amount"]:
                reason = "amount_over_cap"
            elif not (agent["hour_lo"] <= hour <= agent["hour_hi"]):
                reason = "outside_hours"
            events.append(
                {
                    "transaction_id": str(row.get("transaction_id", i)),
                    "agent_id": agent["agent_id"],
                    "tool": agent["tool"],
                    "intent": "pay",
                    "in_scope": in_scope,
                    "reason": reason,
                }
            )
        return out, events

    out = out.reset_index(drop=True)
    for i, row in out.iterrows():
        intent_id = f"intent-{row.get('customer_id', i)}"
        amt_dev = abs(float(row.get("amount_deviation", 0.0)))
        match = amt_dev < 0.25
        out.at[i, "intent_id"] = intent_id
        out.at[i, "intent_match"] = 1.0 if match else 0.0
        events.append(
            {
                "transaction_id": str(row.get("transaction_id", i)),
                "agent_id": "",
                "tool": "pay",
                "intent": f"category:{row.get('merchant_category', 'W')}",
                "in_scope": bool(match),
                "reason": "intent_match" if match else "intent_mismatch",
            }
        )
    return out, events


def agent_events_from_frame(df: pd.DataFrame) -> list[dict[str, Any]]:
    stored = df.attrs.get("agent_events")
    if stored:
        return list(stored)
    return []
