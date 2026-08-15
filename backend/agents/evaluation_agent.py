"""Closed-loop metrics: attack success, F1 lift, false-positive rate."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import f1_score, precision_score, recall_score, roc_auc_score

from features import feature_matrix


class EvaluationAgent:
    def __init__(self, detector) -> None:
        self.detector = detector

    def evaluate_attack_success(
        self,
        attacks: pd.DataFrame | np.ndarray,
        threshold: float | None = None,
    ) -> dict[str, Any]:
        threshold = float(threshold if threshold is not None else self.detector.threshold)
        scores = np.asarray(self.detector.predict(attacks), dtype=float)
        bypassed = scores < threshold
        return {
            "attack_success_rate": float(bypassed.mean()) if len(scores) else 0.0,
            "attacks_detected": int((~bypassed).sum()),
            "attacks_bypassed": int(bypassed.sum()),
            "total_attacks": int(len(scores)),
            "mean_score": float(scores.mean()) if len(scores) else 0.0,
            "threshold": threshold,
        }

    def evaluate_detection_improvement(
        self,
        metrics_before: dict[str, float],
        metrics_after: dict[str, float],
    ) -> dict[str, dict[str, float]]:
        improvement: dict[str, dict[str, float]] = {}
        for metric in ["f1", "precision", "recall", "roc_auc"]:
            before = float(metrics_before.get(metric, 0.0))
            after = float(metrics_after.get(metric, 0.0))
            denom = before if abs(before) > 1e-9 else 1e-9
            improvement[metric] = {
                "before": before,
                "after": after,
                "improvement_pct": ((after - before) / denom) * 100.0,
            }
        return improvement

    def evaluate_false_positive_rate(
        self,
        X_normal: pd.DataFrame,
        threshold: float | None = None,
    ) -> float:
        threshold = float(threshold if threshold is not None else self.detector.threshold)
        scores = self.detector.predict(X_normal)
        return float((scores >= threshold).mean())

    def classification_metrics(
        self,
        X: pd.DataFrame,
        y: pd.Series | np.ndarray,
        threshold: float | None = None,
    ) -> dict[str, float]:
        threshold = float(threshold if threshold is not None else self.detector.threshold)
        proba = self.detector.predict(feature_matrix(X) if isinstance(X, pd.DataFrame) else X)
        pred = (proba >= threshold).astype(int)
        y = np.asarray(y).astype(int)
        return {
            "f1": float(f1_score(y, pred, zero_division=0)),
            "precision": float(precision_score(y, pred, zero_division=0)),
            "recall": float(recall_score(y, pred, zero_division=0)),
            "roc_auc": float(roc_auc_score(y, proba)) if len(np.unique(y)) > 1 else 0.0,
            "fpr": float(((pred == 1) & (y == 0)).sum() / max((y == 0).sum(), 1)),
            "threshold": threshold,
        }


__all__ = ["EvaluationAgent"]
