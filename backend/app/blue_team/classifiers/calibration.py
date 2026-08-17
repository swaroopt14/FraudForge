"""Calibration helper. Does not refit or overwrite BLUE-0.1.0."""

from __future__ import annotations

import numpy as np
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import brier_score_loss


def brier(y_true: np.ndarray, proba: np.ndarray) -> float:
    return float(brier_score_loss(y_true, proba))


class ProbabilityCalibrator:
    """Maps raw P(fraud) → calibrated probability. Fit on a train holdout, never on test labels used for metrics."""

    def __init__(self) -> None:
        self.iso = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)
        self.fitted = False
        self.brier_before: float | None = None
        self.brier_after: float | None = None

    def fit(self, y_true: np.ndarray, proba: np.ndarray) -> "ProbabilityCalibrator":
        y = np.asarray(y_true, dtype=float)
        p = np.asarray(proba, dtype=float)
        if len(y) < 16 or len(np.unique(y)) < 2:
            return self
        self.brier_before = brier(y, p)
        try:
            self.iso.fit(p, y)
            self.fitted = True
            self.brier_after = brier(y, self.transform(p))
        except Exception:  # noqa: BLE001
            self.fitted = False
        return self

    def transform(self, proba: np.ndarray) -> np.ndarray:
        p = np.asarray(proba, dtype=float)
        if not self.fitted:
            return p
        return np.clip(np.asarray(self.iso.predict(p), dtype=float), 0.0, 1.0)
