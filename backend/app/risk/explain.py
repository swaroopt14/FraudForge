"""SHAP (tree) or coefficient fallback."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from app.core.config import FEATURE_COLUMNS
from app.fraud.pipeline import feature_matrix


def explain_row(model: Any, row: pd.DataFrame, top_k: int = 4) -> list[dict[str, Any]]:
    frame = feature_matrix(row).iloc[[0]]
    names = list(FEATURE_COLUMNS)
    values = None
    try:
        import shap

        explainer = shap.TreeExplainer(model)
        sv = explainer.shap_values(frame)
        if isinstance(sv, list):
            sv = sv[1]
        values = np.asarray(sv).reshape(-1)
    except Exception:  # noqa: BLE001
        if hasattr(model, "feature_importances_"):
            values = np.asarray(model.feature_importances_, dtype=float) * np.sign(frame.to_numpy().reshape(-1))
        elif hasattr(model, "named_steps") and hasattr(model.named_steps.get("clf"), "coef_"):
            coef = model.named_steps["clf"].coef_.reshape(-1)
            values = coef * frame.to_numpy().reshape(-1)
        else:
            values = frame.to_numpy().reshape(-1)
    order = np.argsort(np.abs(values))[::-1][:top_k]
    out = []
    for i in order:
        out.append(
            {
                "feature": names[int(i)],
                "shap_value": float(values[int(i)]),
                "value": float(frame.iloc[0, int(i)]),
            }
        )
    return out
