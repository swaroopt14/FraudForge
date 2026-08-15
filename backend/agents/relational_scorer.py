"""Relational fraud head: GraphSAGE-style neighbor stats, optional Torch GCN.

ULB rows have no native merchant/account IDs, so we hash overlay + amount/time
bins into payee / device / account keys. Same-payee clusters act as mule rings.
The tree detector stays unchanged; this head is blended at score time.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

from features import ensure_narrative

GRAPH_FEATURES = [
    "payee_degree",
    "device_degree",
    "payee_mule_mean",
    "device_new_share",
    "ring_amount_mean",
]


def _try_torch():
    try:
        import torch
        import torch.nn as nn

        return torch, nn
    except Exception:  # noqa: BLE001
        return None


def attach_entities(df: pd.DataFrame) -> pd.DataFrame:
    out = ensure_narrative(df).copy()
    mule_bin = np.clip((out["mule_account_risk"].to_numpy(dtype=float) * 10).astype(int), 0, 10)
    hour_bin = np.clip((out["hour_of_day"].to_numpy(dtype=float) / 3.0).astype(int), 0, 8)
    amt_bin = np.clip(np.log1p(out["Amount"].to_numpy(dtype=float)).astype(int), 0, 12)
    out["payee_id"] = (
        mule_bin.astype(str)
        + ":"
        + out["beneficiary_name_match"].astype(int).astype(str)
        + ":"
        + out["constraint_violation"].astype(int).astype(str)
    )
    out["device_id"] = (
        out["device_new"].astype(int).astype(str)
        + ":"
        + out["location_mismatch"].astype(int).astype(str)
        + ":"
        + hour_bin.astype(str)
    )
    out["account_id"] = hour_bin.astype(str) + ":" + amt_bin.astype(str)
    return out


def graph_feature_frame(df: pd.DataFrame) -> pd.DataFrame:
    work = attach_entities(df)
    work = work.loc[:, ~work.columns.duplicated()].copy()
    drop = [c for c in GRAPH_FEATURES if c in work.columns]
    if drop:
        work = work.drop(columns=drop)
    payee_deg = work.groupby("payee_id")["Amount"].transform("size")
    device_deg = work.groupby("device_id")["Amount"].transform("size")
    payee_mule = work.groupby("payee_id")["mule_account_risk"].transform("mean")
    device_new_share = work.groupby("device_id")["device_new"].transform("mean")
    ring_amt = work.groupby("payee_id")["Amount"].transform("mean")
    feats = pd.DataFrame(
        {
            "payee_degree": payee_deg.astype(float),
            "device_degree": device_deg.astype(float),
            "payee_mule_mean": payee_mule.astype(float),
            "device_new_share": device_new_share.astype(float),
            "ring_amount_mean": ring_amt.astype(float),
        },
        index=work.index,
    )
    return pd.concat([work, feats], axis=1)


class _TinyGCN:
    """Two-layer GCN on payee nodes. Trained only when Torch is importable."""

    def __init__(self, in_dim: int, hidden: int = 8) -> None:
        torch, nn = _try_torch()
        if torch is None:
            raise RuntimeError("torch missing")
        self.torch = torch
        self.lin1 = nn.Linear(in_dim, hidden)
        self.lin2 = nn.Linear(hidden, 1)
        self.opt = torch.optim.Adam(list(self.lin1.parameters()) + list(self.lin2.parameters()), lr=0.05)

    def _norm_adj(self, a: "object") -> "object":
        torch = self.torch
        deg = a.sum(dim=1).clamp(min=1.0)
        d_inv = torch.diag(deg.pow(-0.5))
        return d_inv @ a @ d_inv

    def fit(self, x: np.ndarray, adj: np.ndarray, y: np.ndarray, epochs: int = 25) -> None:
        torch = self.torch
        xt = torch.tensor(x, dtype=torch.float32)
        at = self._norm_adj(torch.tensor(adj, dtype=torch.float32))
        yt = torch.tensor(y, dtype=torch.float32).view(-1, 1)
        loss_fn = torch.nn.BCEWithLogitsLoss()
        for _ in range(epochs):
            self.opt.zero_grad()
            h = torch.relu(at @ self.lin1(xt))
            logit = self.lin2(at @ h)
            loss = loss_fn(logit, yt)
            loss.backward()
            self.opt.step()

    def predict(self, x: np.ndarray, adj: np.ndarray) -> np.ndarray:
        torch = self.torch
        with torch.no_grad():
            xt = torch.tensor(x, dtype=torch.float32)
            at = self._norm_adj(torch.tensor(adj, dtype=torch.float32))
            h = torch.relu(at @ self.lin1(xt))
            logit = self.lin2(at @ h)
            return torch.sigmoid(logit).view(-1).numpy()


class RelationalScorer:
    def __init__(self) -> None:
        self.context: pd.DataFrame | None = None
        self.backend = "unfitted"
        self._logreg: LogisticRegression | None = None
        self._gnn: _TinyGCN | None = None
        self._payee_index: dict[str, int] = {}
        self._payee_scores: dict[str, float] = {}
        self.metrics: dict[str, Any] = {}

    def fit_context(self, processed: pd.DataFrame, n: int = 2500, seed: int = 42) -> None:
        if processed is None or processed.empty:
            self.backend = "unfitted"
            return
        rng = np.random.default_rng(seed)
        take = min(n, len(processed))
        if "Class" in processed.columns and processed["Class"].nunique() > 1:
            fraud = processed.loc[processed["Class"] == 1]
            legit = processed.loc[processed["Class"] == 0]
            n_f = min(len(fraud), max(80, take // 8))
            n_l = min(len(legit), take - n_f)
            ctx = pd.concat(
                [
                    fraud.sample(n_f, random_state=seed) if n_f else fraud,
                    legit.sample(n_l, random_state=seed) if n_l else legit,
                ],
                ignore_index=True,
            )
        else:
            idx = rng.choice(len(processed), size=take, replace=False)
            ctx = processed.iloc[idx].copy()
        self.context = graph_feature_frame(ctx)
        self._fit_graphsage()
        self._try_fit_gnn()

    def _design(self, framed: pd.DataFrame) -> pd.DataFrame:
        cols = [
            "mule_account_risk",
            "velocity_1h",
            "device_new",
            "location_mismatch",
            "constraint_violation",
            "amount_vs_limit_ratio",
            *GRAPH_FEATURES,
        ]
        for col in cols:
            if col not in framed.columns:
                framed[col] = 0.0
        return framed[cols].astype(float)

    def _fit_graphsage(self) -> None:
        if self.context is None or "Class" not in self.context.columns:
            self.backend = "message_passing"
            return
        X = self._design(self.context)
        y = self.context["Class"].astype(int).to_numpy()
        if y.min() == y.max():
            self.backend = "message_passing"
            return
        self._logreg = LogisticRegression(max_iter=250, class_weight="balanced")
        self._logreg.fit(X, y)
        self.backend = "graphsage"
        pred = self._logreg.predict_proba(X)[:, 1]
        self.metrics = {
            "n_context": int(len(self.context)),
            "context_auc_proxy": float(np.corrcoef(pred, y)[0, 1]) if y.std() else 0.0,
        }

    def _try_fit_gnn(self) -> None:
        if _try_torch() is None or self.context is None or "Class" not in self.context.columns:
            return
        try:
            payees = list(self.context["payee_id"].astype(str).unique())
            if len(payees) < 8:
                return
            self._payee_index = {p: i for i, p in enumerate(payees)}
            n = len(payees)
            x = np.zeros((n, 5), dtype=np.float32)
            y = np.zeros(n, dtype=np.float32)
            grouped = self.context.groupby("payee_id")
            for payee, part in grouped:
                i = self._payee_index[str(payee)]
                x[i] = [
                    float(np.log1p(part["Amount"].mean())),
                    float(part["mule_account_risk"].mean()),
                    float(part["velocity_1h"].mean()),
                    float(part["device_new"].mean()),
                    float(len(part)),
                ]
                y[i] = float(part["Class"].max()) if "Class" in part.columns else 0.0
            # Edges: payees that share an account_id
            adj = np.eye(n, dtype=np.float32)
            for _, part in self.context.groupby("account_id"):
                nodes = [self._payee_index[str(p)] for p in part["payee_id"].astype(str).unique() if str(p) in self._payee_index]
                for a in nodes:
                    for b in nodes:
                        adj[a, b] = 1.0
            gnn = _TinyGCN(in_dim=5)
            gnn.fit(x, adj, y, epochs=20)
            scores = gnn.predict(x, adj)
            self._gnn = gnn
            self._payee_scores = {p: float(scores[i]) for p, i in self._payee_index.items()}
            self.backend = "gcn"
            self.metrics["gnn_nodes"] = n
        except Exception:  # noqa: BLE001
            self._gnn = None

    def score(self, rows: pd.DataFrame) -> dict[str, Any]:
        query = graph_feature_frame(rows)
        if self.context is not None:
            combined = graph_feature_frame(pd.concat([self.context, query], ignore_index=True))
            query = combined.iloc[-len(query) :].reset_index(drop=True)
        else:
            query = query.reset_index(drop=True)

        if self._logreg is not None:
            rel = self._logreg.predict_proba(self._design(query))[:, 1]
        else:
            rel = (
                0.40 * query["payee_mule_mean"].to_numpy(dtype=float)
                + 0.20 * np.clip(query["payee_degree"].to_numpy(dtype=float) / 12.0, 0, 1)
                + 0.25 * query["mule_account_risk"].to_numpy(dtype=float)
                + 0.15 * query["device_new"].to_numpy(dtype=float)
            )
            rel = np.clip(rel, 0.0, 1.0)

        gnn_scores = None
        if self._payee_scores:
            gnn_scores = np.array(
                [self._payee_scores.get(str(p), float(rel[i])) for i, p in enumerate(query["payee_id"])],
                dtype=float,
            )
            rel = 0.55 * rel + 0.45 * gnn_scores

        details = []
        for i in range(len(query)):
            item = {
                "payee_id": str(query.iloc[i]["payee_id"]),
                "device_id": str(query.iloc[i]["device_id"]),
                "payee_degree": float(query.iloc[i]["payee_degree"]),
                "device_degree": float(query.iloc[i]["device_degree"]),
                "payee_mule_mean": float(query.iloc[i]["payee_mule_mean"]),
                "device_new_share": float(query.iloc[i]["device_new_share"]),
                "relational_score": float(rel[i]),
            }
            if gnn_scores is not None:
                item["gcn_score"] = float(gnn_scores[i])
            details.append(item)
        return {
            "backend": self.backend,
            "scores": rel.tolist(),
            "details": details,
        }


__all__ = ["GRAPH_FEATURES", "RelationalScorer", "attach_entities", "graph_feature_frame"]
