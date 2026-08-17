"""Relationship graph from a payment stream. No GNN."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

import pandas as pd


def build_edges(df: pd.DataFrame) -> list[dict[str, str]]:
    edges: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for _, row in df.iterrows():
        cust = str(row.get("customer_id") or "unknown")
        ben = str(row.get("beneficiary_id") or "unknown")
        device = str(row.get("device_id") or "unknown")
        ip = str(row.get("ip_id") or "unknown")
        merch = str(row.get("merchant_id") or "unknown")
        triples = [
            (cust, "PAID", ben),
            (cust, "USED", device),
            (cust, "CONNECTED", ip),
            (cust, "SENT_TO", merch),
        ]
        for src, rel, dst in triples:
            key = (src, rel, dst)
            if key in seen:
                continue
            seen.add(key)
            edges.append({"source": src, "relation": rel, "target": dst})
    return edges


def neighborhood(df: pd.DataFrame, entity_id: str, limit: int = 80) -> dict[str, Any]:
    """Nodes/edges around a customer, beneficiary, device, or IP."""
    eid = str(entity_id)
    mask = (
        (df.get("customer_id", pd.Series(dtype=str)).astype(str) == eid)
        | (df.get("beneficiary_id", pd.Series(dtype=str)).astype(str) == eid)
        | (df.get("device_id", pd.Series(dtype=str)).astype(str) == eid)
        | (df.get("ip_id", pd.Series(dtype=str)).astype(str) == eid)
        | (df.get("merchant_id", pd.Series(dtype=str)).astype(str) == eid)
    )
    sub = df.loc[mask].head(limit)
    nodes: dict[str, str] = {}
    for _, row in sub.iterrows():
        nodes[str(row.get("customer_id"))] = "customer"
        nodes[str(row.get("beneficiary_id"))] = "beneficiary"
        nodes[str(row.get("device_id"))] = "device"
        nodes[str(row.get("ip_id"))] = "ip"
        nodes[str(row.get("merchant_id"))] = "merchant"
    edges = build_edges(sub)
    return {
        "entity_id": eid,
        "nodes": [{"id": k, "type": v} for k, v in nodes.items() if k and k != "nan"],
        "edges": edges,
        "transaction_count": int(len(sub)),
    }


def cluster_stats(df: pd.DataFrame) -> dict[str, int]:
    if df.empty:
        return {
            "high_risk_clusters": 0,
            "shared_devices": 0,
            "shared_ips": 0,
            "suspicious_beneficiaries": 0,
            "mule_networks": 0,
        }
    from app.blue_team.features import attach_p2_features

    feat = attach_p2_features(df)
    return {
        "high_risk_clusters": int((feat["mule_cluster_score"] >= 0.6).sum()),
        "shared_devices": int(feat.loc[feat["device_is_shared"] >= 1.0, "device_id"].nunique())
        if "device_id" in feat.columns
        else 0,
        "shared_ips": int(feat.loc[feat["ip_is_shared"] >= 1.0, "ip_id"].nunique()) if "ip_id" in feat.columns else 0,
        "suspicious_beneficiaries": int(feat.loc[feat["beneficiary_fan_in"] >= 8.0, "beneficiary_id"].nunique())
        if "beneficiary_id" in feat.columns
        else 0,
        "mule_networks": int(feat.loc[feat["mule_cluster_score"] >= 0.75, "beneficiary_id"].nunique())
        if "beneficiary_id" in feat.columns
        else int((feat["mule_cluster_score"] >= 0.75).any()),
    }


def beneficiary_profile(df: pd.DataFrame, beneficiary_id: str) -> dict[str, Any]:
    eid = str(beneficiary_id)
    if df.empty or "beneficiary_id" not in df.columns:
        return {"entity_id": eid, "found": False}
    sub = df.loc[df["beneficiary_id"].astype(str) == eid]
    if sub.empty:
        return {"entity_id": eid, "found": False}
    from app.blue_team.features import attach_p2_features

    feat = attach_p2_features(df)
    hit = feat.loc[feat["beneficiary_id"].astype(str) == eid]
    fan = float(hit["beneficiary_fan_in"].iloc[0]) if len(hit) else float(sub["customer_id"].nunique())
    return {
        "entity_id": eid,
        "found": True,
        "entity_type": "beneficiary",
        "connected_customers": int(sub["customer_id"].nunique()) if "customer_id" in sub.columns else 0,
        "devices": int(sub["device_id"].nunique()) if "device_id" in sub.columns else 0,
        "ips": int(sub["ip_id"].nunique()) if "ip_id" in sub.columns else 0,
        "transactions": int(len(sub)),
        "total_value": float(pd.to_numeric(sub["amount"], errors="coerce").fillna(0).sum()) if "amount" in sub.columns else 0.0,
        "fan_in": fan,
        "first_seen": float(pd.to_numeric(sub["timestamp"], errors="coerce").min()) if "timestamp" in sub.columns else None,
    }
