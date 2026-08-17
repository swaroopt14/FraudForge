"""Real edge table from payment rows. No GNN — typed relations plus an attack-focus view."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

import numpy as np
import pandas as pd

RELATIONS = (
    ("customer", "customer_id", "device", "device_id", "uses_device"),
    ("customer", "customer_id", "ip", "ip_id", "uses_ip"),
    ("customer", "customer_id", "merchant", "merchant_id", "pays_merchant"),
    ("customer", "customer_id", "beneficiary", "beneficiary_id", "pays_beneficiary"),
    ("device", "device_id", "ip", "ip_id", "connected_from"),
    ("customer", "customer_id", "geo", "country", "located_in"),
)

_NEW_MARKERS = ("mut-", "ato-", "mule-", "shared-", "new-ben", "new-merch")

FAMILY_PATHS: dict[str, list[dict[str, str]]] = {
    "account_takeover": [
        {"id": "account", "label": "Account", "type": "customer"},
        {"id": "new_device", "label": "New device", "type": "device"},
        {"id": "new_geo", "label": "New location", "type": "ip"},
        {"id": "takeover", "label": "Account takeover", "type": "customer"},
        {"id": "new_ben", "label": "New beneficiary", "type": "beneficiary"},
        {"id": "txn", "label": "Suspicious transaction", "type": "transaction"},
    ],
    "mule_network": [
        {"id": "accounts", "label": "Many accounts", "type": "customer"},
        {"id": "fan_in", "label": "Shared mule sink", "type": "beneficiary"},
        {"id": "txn", "label": "Fan-in transfers", "type": "transaction"},
    ],
    "shared_device": [
        {"id": "accounts", "label": "Many accounts", "type": "customer"},
        {"id": "device", "label": "Shared device", "type": "device"},
        {"id": "txn", "label": "Coordinated spend", "type": "transaction"},
    ],
    "shared_ip": [
        {"id": "accounts", "label": "Many accounts", "type": "customer"},
        {"id": "ip", "label": "Shared IP", "type": "ip"},
        {"id": "txn", "label": "Coordinated spend", "type": "transaction"},
    ],
    "beneficiary_anomaly": [
        {"id": "account", "label": "Known account", "type": "customer"},
        {"id": "new_ben", "label": "New beneficiary", "type": "beneficiary"},
        {"id": "txn", "label": "First-time transfer", "type": "transaction"},
    ],
    "velocity_attack": [
        {"id": "account", "label": "Account", "type": "customer"},
        {"id": "burst", "label": "Velocity burst", "type": "transaction"},
        {"id": "merchants", "label": "Merchant spray", "type": "merchant"},
    ],
    "agent_scope": [
        {"id": "agent", "label": "Agent", "type": "agent"},
        {"id": "account", "label": "Account", "type": "customer"},
        {"id": "out_of_scope", "label": "Out-of-scope destination", "type": "beneficiary"},
    ],
}


def build_edge_table(df: pd.DataFrame, max_edges: int = 4000) -> list[dict[str, Any]]:
    edges: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str, str]] = set()
    for src_t, src_c, dst_t, dst_c, rel in RELATIONS:
        if src_c not in df.columns or dst_c not in df.columns:
            continue
        pairs = df[[src_c, dst_c]].dropna().drop_duplicates()
        for src, dst in pairs.itertuples(index=False):
            key = (src_t, str(src), dst_t, str(dst), rel)
            if key in seen:
                continue
            seen.add(key)
            edges.append(
                {
                    "src_type": src_t,
                    "src_id": str(src),
                    "dst_type": dst_t,
                    "dst_id": str(dst),
                    "relation": rel,
                    "weight": 1.0,
                }
            )
            if len(edges) >= max_edges:
                return edges
    return edges


def graph_payload(
    df: pd.DataFrame,
    max_nodes: int = 80,
    max_edges: int = 160,
    *,
    family: str = "",
    attack_id: str = "",
    variant_id: str = "",
    scores: np.ndarray | None = None,
) -> dict[str, Any]:
    edges = build_edge_table(df)
    degree: Counter[str] = Counter()
    for edge in edges:
        degree[f"{edge['src_type']}:{edge['src_id']}"] += 1
        degree[f"{edge['dst_type']}:{edge['dst_id']}"] += 1
    top = {node for node, _ in degree.most_common(max_nodes)}
    nodes = []
    for key in sorted(top):
        ntype, nid = key.split(":", 1)
        nodes.append({"id": key, "type": ntype, "label": _short(nid), "degree": int(degree[key])})
    keep = {n["id"] for n in nodes}
    vis_edges = []
    for edge in edges:
        src = f"{edge['src_type']}:{edge['src_id']}"
        dst = f"{edge['dst_type']}:{edge['dst_id']}"
        if src in keep and dst in keep:
            vis_edges.append({**edge, "source": src, "target": dst})
        if len(vis_edges) >= max_edges:
            break
    shared = _shared_hubs(edges)
    work = df.copy()
    if scores is not None and len(work):
        work["_score"] = np.asarray(scores, dtype=float)[: len(work)]
        work["_detected"] = work["_score"] >= 0.5
    elif "fraud_probability" in work.columns:
        work["_score"] = pd.to_numeric(work["fraud_probability"], errors="coerce").fillna(0.0)
        work["_detected"] = work["_score"] >= 0.5
    flags = _row_flags(work)
    path = _attack_path(family, flags, work)
    return {
        "nodes": nodes,
        "edges": vis_edges,
        "edge_table": edges[:2000],
        "n_edges": len(edges),
        "n_nodes": len(degree),
        "shared_hubs": shared,
        "attack_networks": int(len(shared)),
        "family": family,
        "attack_id": attack_id,
        "variant_id": variant_id,
        "stats": _attack_stats(work, edges, flags, shared),
        "focus": _focus_subgraph(work, edges, flags, family, shared),
        "path": path,
        "blue": _blue_status(path),
        "motif": _motif(family, flags),
    }


def _short(value: str, n: int = 14) -> str:
    text = str(value)
    return text if len(text) <= n else text[: n - 1] + "…"


def _marked(value: Any) -> bool:
    text = str(value).lower()
    return any(text.startswith(mark) or mark in text for mark in _NEW_MARKERS)


def _row_flags(df: pd.DataFrame) -> pd.DataFrame:
    n = len(df)
    empty = pd.DataFrame(
        {
            "new_device": pd.Series(dtype=bool),
            "new_ip": pd.Series(dtype=bool),
            "new_ben": pd.Series(dtype=bool),
            "new_merchant": pd.Series(dtype=bool),
            "failed_auth": pd.Series(dtype=bool),
            "geo": pd.Series(dtype=bool),
            "detected": pd.Series(dtype=bool),
        }
    )
    if not n:
        return empty
    device_age = pd.to_numeric(df["device_age_days"], errors="coerce").fillna(1.0) if "device_age_days" in df.columns else pd.Series(1.0, index=df.index)
    ben_new = pd.to_numeric(df["beneficiary_is_new"], errors="coerce").fillna(0.0) if "beneficiary_is_new" in df.columns else pd.Series(0.0, index=df.index)
    failed = pd.to_numeric(df["failed_auth_count"], errors="coerce").fillna(0.0) if "failed_auth_count" in df.columns else pd.Series(0.0, index=df.index)
    distance = pd.to_numeric(df["distance_from_home"], errors="coerce").fillna(0.0) if "distance_from_home" in df.columns else pd.Series(0.0, index=df.index)
    device_id = df["device_id"] if "device_id" in df.columns else pd.Series("", index=df.index)
    ip_id = df["ip_id"] if "ip_id" in df.columns else pd.Series("", index=df.index)
    ben_id = df["beneficiary_id"] if "beneficiary_id" in df.columns else pd.Series("", index=df.index)
    merch_id = df["merchant_id"] if "merchant_id" in df.columns else pd.Series("", index=df.index)
    return pd.DataFrame(
        {
            "new_device": (device_age <= 0) | device_id.map(_marked).astype(bool),
            "new_ip": ip_id.map(_marked).astype(bool),
            "new_ben": (ben_new > 0) | ben_id.map(_marked).astype(bool),
            "new_merchant": merch_id.map(_marked).astype(bool),
            "failed_auth": failed >= 1,
            "geo": distance >= 8,
            "detected": df["_detected"].astype(bool) if "_detected" in df.columns else False,
        },
        index=df.index,
    )


def _attack_stats(
    df: pd.DataFrame,
    edges: list[dict[str, Any]],
    flags: pd.DataFrame,
    shared: list[dict[str, Any]],
) -> dict[str, int]:
    node_ids = {f"{e['src_type']}:{e['src_id']}" for e in edges} | {f"{e['dst_type']}:{e['dst_id']}" for e in edges}
    attack_mask = flags[["new_device", "new_ip", "new_ben", "failed_auth", "geo"]].any(axis=1) if len(flags) else pd.Series(dtype=bool)
    attack_customers = int(df.loc[attack_mask, "customer_id"].nunique()) if len(df) and "customer_id" in df.columns and attack_mask.any() else 0
    return {
        "n_nodes": int(len(node_ids)),
        "n_edges": int(len(edges)),
        "shared_hubs": int(len(shared)),
        "compromised_accounts": attack_customers,
        "new_devices": int(df.loc[flags["new_device"], "device_id"].nunique()) if len(df) and "device_id" in df.columns and "new_device" in flags else 0,
        "new_beneficiaries": int(df.loc[flags["new_ben"], "beneficiary_id"].nunique()) if len(df) and "beneficiary_id" in df.columns and "new_ben" in flags else 0,
        "new_ips": int(df.loc[flags["new_ip"], "ip_id"].nunique()) if len(df) and "ip_id" in df.columns and "new_ip" in flags else 0,
    }


def _focus_subgraph(
    df: pd.DataFrame,
    edges: list[dict[str, Any]],
    flags: pd.DataFrame,
    family: str,
    shared: list[dict[str, Any]],
) -> dict[str, Any]:
    if df is None or not len(df) or "customer_id" not in df.columns:
        return {"nodes": [], "edges": [], "n_nodes": 0, "n_edges": 0}
    score = flags[["new_device", "new_ip", "new_ben", "failed_auth", "geo"]].astype(int).sum(axis=1)
    if "_score" in df.columns:
        score = score + (1.0 - pd.to_numeric(df["_score"], errors="coerce").fillna(0.0)).clip(0, 1)
    ranked = (
        pd.DataFrame({"customer_id": df["customer_id"].astype(str), "score": score})
        .groupby("customer_id", sort=False)["score"]
        .mean()
        .sort_values(ascending=False)
    )
    seed_customers = list(ranked.head(8).index)
    if family in {"mule_network", "shared_device", "shared_ip"} and shared:
        hub = shared[0]
        hub_customers = {
            e["src_id"]
            for e in edges
            if e["dst_type"] == hub["type"] and e["dst_id"] == hub["id"] and e["src_type"] == "customer"
        }
        seed_customers = list(hub_customers)[:10] or seed_customers
    keep_ids: set[str] = {f"customer:{cid}" for cid in seed_customers}
    for edge in edges:
        if edge["src_id"] in seed_customers and edge["src_type"] == "customer":
            keep_ids.add(f"{edge['src_type']}:{edge['src_id']}")
            keep_ids.add(f"{edge['dst_type']}:{edge['dst_id']}")
    if len(keep_ids) > 28:
        preferred = [key for key in keep_ids if key.startswith("customer:") or any(mark in key.lower() for mark in _NEW_MARKERS)]
        keep_ids = set((preferred or list(keep_ids))[:28])
    focus_edges = []
    for edge in edges:
        src = f"{edge['src_type']}:{edge['src_id']}"
        dst = f"{edge['dst_type']}:{edge['dst_id']}"
        if src in keep_ids and dst in keep_ids:
            focus_edges.append({**edge, "source": src, "target": dst, "label": _relation_label(edge["relation"])})
        if len(focus_edges) >= 40:
            break
    used = {e["source"] for e in focus_edges} | {e["target"] for e in focus_edges} or keep_ids
    detected_by_customer: dict[str, float] = {}
    if "_detected" in df.columns:
        detected_by_customer = df.groupby(df["customer_id"].astype(str))["_detected"].mean().astype(float).to_dict()
    nodes = []
    for key in sorted(used):
        ntype, nid = key.split(":", 1)
        role, flag = _role_for(ntype, nid, family)
        detected = None
        if ntype == "customer":
            frac = float(detected_by_customer.get(nid, -1))
            detected = None if frac < 0 else frac >= 0.5
        nodes.append({"id": key, "type": ntype, "label": _short(nid, 12), "role": role, "flag": flag, "detected": detected})
    return {"nodes": nodes, "edges": focus_edges, "n_nodes": len(nodes), "n_edges": len(focus_edges)}


def _relation_label(relation: str) -> str:
    return {
        "uses_device": "uses",
        "uses_ip": "from",
        "pays_beneficiary": "pays",
        "pays_merchant": "shops",
    }.get(relation, relation.replace("_", " "))


def _role_for(ntype: str, nid: str, family: str) -> tuple[str, str]:
    marked = _marked(nid)
    if ntype == "device":
        if family == "shared_device":
            return "shared device", "shared"
        return ("new device" if marked else "device", "new" if marked else "normal")
    if ntype == "ip":
        if family == "shared_ip":
            return "shared IP", "shared"
        return ("new location" if marked else "IP", "new" if marked else "normal")
    if ntype == "beneficiary":
        if family == "mule_network":
            return "mule sink", "shared"
        return ("new beneficiary" if marked else "beneficiary", "new" if marked else "normal")
    if ntype == "merchant":
        return "merchant", "new" if marked else "normal"
    if ntype == "agent":
        return "agent", "normal"
    return "account", "normal"


def _attack_path(family: str, flags: pd.DataFrame, df: pd.DataFrame) -> list[dict[str, Any]]:
    steps = [dict(step) for step in FAMILY_PATHS.get(family, [
        {"id": "account", "label": "Account", "type": "customer"},
        {"id": "txn", "label": "Attack transactions", "type": "transaction"},
    ])]
    detected_frac = float(df["_detected"].mean()) if len(df) and "_detected" in df.columns else None
    has = {
        "new_device": bool(flags["new_device"].any()) if len(flags) else False,
        "new_geo": bool((flags["new_ip"] | flags["geo"]).any()) if len(flags) else False,
        "new_ben": bool(flags["new_ben"].any()) if len(flags) else False,
    }
    for step in steps:
        key = step["id"]
        if key == "new_device":
            step["present"] = has["new_device"]
            step["status"] = _step_status(df, flags["new_device"] if len(flags) else None, detected_frac)
        elif key in {"new_geo", "ip"}:
            mask = (flags["new_ip"] | flags["geo"]) if len(flags) else None
            step["present"] = has["new_geo"]
            step["status"] = _step_status(df, mask, detected_frac)
        elif key in {"new_ben", "out_of_scope", "fan_in"}:
            step["present"] = has["new_ben"] or family in {"mule_network", "agent_scope"}
            step["status"] = _step_status(df, flags["new_ben"] if len(flags) else None, detected_frac)
        elif key == "device":
            step["present"] = True
            step["status"] = _step_status(df, flags["new_device"] if len(flags) else None, detected_frac)
        else:
            step["present"] = True
            step["status"] = "detected" if detected_frac is not None and detected_frac >= 0.5 else "missed" if detected_frac is not None else "unknown"
    return steps


def _step_status(df: pd.DataFrame, mask: pd.Series | None, fallback: float | None) -> str:
    if mask is not None and len(df) and "_detected" in df.columns and bool(mask.any()):
        frac = float(df.loc[mask, "_detected"].mean())
        return "detected" if frac >= 0.5 else "missed"
    if fallback is None:
        return "unknown"
    return "detected" if fallback >= 0.5 else "missed"


def _blue_status(path: list[dict[str, Any]]) -> list[dict[str, str]]:
    return [{"label": step["label"], "status": str(step.get("status") or "unknown")} for step in path]


def _motif(family: str, flags: pd.DataFrame) -> list[dict[str, Any]]:
    items = [
        ("new_device", "New device", bool(flags["new_device"].any()) if len(flags) else False),
        ("new_geo", "Geo / IP change", bool((flags["new_ip"] | flags["geo"]).any()) if len(flags) else False),
        ("new_ben", "New beneficiary", bool(flags["new_ben"].any()) if len(flags) else False),
        ("failed_auth", "Failed auth", bool(flags["failed_auth"].any()) if len(flags) else False),
        ("shared", "Shared hub", family in {"mule_network", "shared_device", "shared_ip"}),
    ]
    if family == "account_takeover":
        keep = {"new_device", "new_geo", "failed_auth", "new_ben"}
        items = [row for row in items if row[0] in keep]
    return [{"id": i, "label": label, "present": present} for i, label, present in items]


def _shared_hubs(edges: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_hub: dict[tuple[str, str], set[str]] = defaultdict(set)
    for edge in edges:
        if edge["relation"] in {"uses_device", "uses_ip", "pays_beneficiary", "pays_merchant"}:
            by_hub[(edge["dst_type"], edge["dst_id"])].add(edge["src_id"])
    hubs = []
    for (ntype, nid), customers in by_hub.items():
        if len(customers) >= 2:
            hubs.append({"type": ntype, "id": nid, "customers": len(customers)})
    hubs.sort(key=lambda h: -h["customers"])
    return hubs[:40]


def network_fidelity(attack_edges: list[dict[str, Any]], legit_edges: list[dict[str, Any]]) -> float:
    def _degrees(edges: list[dict[str, Any]]) -> np.ndarray:
        c: Counter[str] = Counter()
        for edge in edges:
            c[f"{edge['dst_type']}:{edge['dst_id']}"] += 1
        vals = np.array(list(c.values()), dtype=float)
        return vals if len(vals) else np.array([0.0])

    a = np.sort(_degrees(attack_edges))
    b = np.sort(_degrees(legit_edges))
    n = max(len(a), len(b), 1)
    if len(a) < n:
        a = np.pad(a, (0, n - len(a)))
    if len(b) < n:
        b = np.pad(b, (0, n - len(b)))
    scale = max(float(b.std() or 1.0), 1.0)
    dist = float(np.mean(np.abs(a - b)))
    return float(np.clip(1.0 - dist / scale, 0.0, 1.0))


def edge_fingerprint(edges: list[dict[str, Any]]) -> list[str]:
    return sorted(f"{e['src_type']}|{e['src_id']}|{e['dst_type']}|{e['dst_id']}|{e['relation']}" for e in edges)
