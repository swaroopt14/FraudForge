"""XGBoost fraud detector with threshold tuning and SHAP explanations."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import (
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split

try:
    import xgboost as xgb

    HAS_XGBOOST = True
except Exception:  # noqa: BLE001
    xgb = None
    HAS_XGBOOST = False

try:
    import lightgbm as lgb

    HAS_LIGHTGBM = True
except Exception:  # noqa: BLE001
    lgb = None
    HAS_LIGHTGBM = False

from config import DETECTOR_PATH, FEATURE_COLUMNS, MODELS_DIR, RANDOM_STATE
from features import ensure_narrative, feature_matrix


def _fpr(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    neg = y_true == 0
    if neg.sum() == 0:
        return 0.0
    return float(((y_pred == 1) & neg).sum() / neg.sum())


def best_threshold(y_true: np.ndarray, proba: np.ndarray) -> tuple[float, float]:
    """Pick a decision threshold that maximizes F1 on the validation split."""
    from sklearn.metrics import precision_recall_curve

    precision, recall, thresholds = precision_recall_curve(y_true, proba)
    if len(thresholds) == 0:
        return 0.5, 0.0
    f1 = 2 * precision[:-1] * recall[:-1] / (precision[:-1] + recall[:-1] + 1e-12)
    idx = int(np.nanargmax(f1))
    return float(thresholds[idx]), float(f1[idx])


class FraudDetector:
    def __init__(self) -> None:
        self.model: Any = None
        self.threshold: float = 0.5
        self.feature_names: list[str] = list(FEATURE_COLUMNS)
        self.metrics: dict[str, float] = {}
        self.shap_explainer = None
        if HAS_XGBOOST:
            self.backend = "xgboost"
        elif HAS_LIGHTGBM:
            self.backend = "lightgbm"
        else:
            self.backend = "hist_gbdt"
        self._feature_means: np.ndarray | None = None

    def _make_model(self, scale_pos_weight: float):
        if HAS_XGBOOST:
            return xgb.XGBClassifier(
                max_depth=6,
                learning_rate=0.1,
                n_estimators=200,
                subsample=0.8,
                colsample_bytree=0.8,
                scale_pos_weight=scale_pos_weight,
                eval_metric="logloss",
                tree_method="hist",
                n_jobs=-1,
                random_state=RANDOM_STATE,
            )
        if HAS_LIGHTGBM:
            return lgb.LGBMClassifier(
                max_depth=6,
                learning_rate=0.1,
                n_estimators=200,
                subsample=0.8,
                colsample_bytree=0.8,
                scale_pos_weight=scale_pos_weight,
                random_state=RANDOM_STATE,
                verbosity=-1,
            )
        # OpenMP-free fallback when libomp is missing (common on macOS).
        return HistGradientBoostingClassifier(
            max_depth=6,
            learning_rate=0.1,
            max_iter=200,
            class_weight="balanced",
            random_state=RANDOM_STATE,
        )

    def train(
        self,
        X: pd.DataFrame,
        y: pd.Series | np.ndarray,
        test_size: float = 0.2,
    ) -> dict[str, float]:
        X = feature_matrix(ensure_narrative(X)) if not set(FEATURE_COLUMNS).issubset(X.columns) else X[FEATURE_COLUMNS]
        y = pd.Series(y).astype(int)
        pos = max(int((y == 1).sum()), 1)
        neg = int((y == 0).sum())
        spw = neg / pos

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, random_state=RANDOM_STATE, stratify=y
        )
        X_fit, X_val, y_fit, y_val = train_test_split(
            X_train, y_train, test_size=0.15, random_state=RANDOM_STATE, stratify=y_train
        )

        self.model = self._make_model(spw)
        self.model.fit(X_fit, y_fit)
        self._feature_means = X_fit.mean(axis=0).to_numpy()
        if HAS_XGBOOST and hasattr(self.model, "get_booster"):
            self.backend = "xgboost"
        elif HAS_LIGHTGBM and type(self.model).__name__.startswith("LGBM"):
            self.backend = "lightgbm"
        else:
            self.backend = "hist_gbdt"
        val_proba = self.model.predict_proba(X_val)[:, 1]
        self.threshold, _ = best_threshold(y_val.to_numpy(), val_proba)

        test_proba = self.model.predict_proba(X_test)[:, 1]
        test_pred = (test_proba >= self.threshold).astype(int)
        self.metrics = {
            "f1": float(f1_score(y_test, test_pred, zero_division=0)),
            "precision": float(precision_score(y_test, test_pred, zero_division=0)),
            "recall": float(recall_score(y_test, test_pred, zero_division=0)),
            "roc_auc": float(roc_auc_score(y_test, test_proba)),
            "fpr": _fpr(y_test.to_numpy(), test_pred),
            "threshold": float(self.threshold),
            "n_train": int(len(X_fit)),
            "n_test": int(len(X_test)),
            "scale_pos_weight": float(spw),
            "backend": self.backend,
        }
        self.feature_names = list(X.columns)
        return self.metrics

    def fit_full(self, X: pd.DataFrame, y: pd.Series | np.ndarray, threshold: float | None = None) -> None:
        """Retrain on an augmented set, keeping a threshold unless a new one is supplied."""
        X = X[self.feature_names] if self.feature_names else X
        y = pd.Series(y).astype(int)
        pos = max(int((y == 1).sum()), 1)
        neg = max(int((y == 0).sum()), 1)
        self.model = self._make_model(neg / pos)
        self.model.fit(X, y)
        self._feature_means = X.mean(axis=0).to_numpy() if hasattr(X, "mean") else np.mean(np.asarray(X), axis=0)
        if threshold is not None:
            self.threshold = float(threshold)

    def predict(self, X: pd.DataFrame | np.ndarray) -> np.ndarray:
        if self.model is None:
            raise RuntimeError("Detector is not trained")
        frame = self._as_frame(X)
        return self.model.predict_proba(frame)[:, 1]

    def predict_label(self, X: pd.DataFrame | np.ndarray) -> np.ndarray:
        return (self.predict(X) >= self.threshold).astype(int)

    def _shap_matrix(self, frame: pd.DataFrame) -> np.ndarray:
        """TreeSHAP via XGBoost pred_contribs, or local mean-impute deltas."""
        if HAS_XGBOOST and hasattr(self.model, "get_booster"):
            dmat = xgb.DMatrix(frame, feature_names=self.feature_names)
            contribs = self.model.get_booster().predict(dmat, pred_contribs=True)
            return np.asarray(contribs)[:, :-1]
        if HAS_LIGHTGBM and hasattr(self.model, "predict"):
            try:
                contribs = np.asarray(self.model.predict(frame, pred_contrib=True))
                if contribs.ndim == 2 and contribs.shape[1] >= len(self.feature_names):
                    return contribs[:, : len(self.feature_names)]
            except Exception:  # noqa: BLE001
                pass
        means = self._feature_means
        if means is None:
            means = frame.mean(axis=0).to_numpy()
        base = self.model.predict_proba(frame)[:, 1]
        values = np.zeros((len(frame), len(self.feature_names)), dtype=float)
        for i, _name in enumerate(self.feature_names):
            alt = frame.copy()
            alt.iloc[:, i] = means[i]
            values[:, i] = base - self.model.predict_proba(alt)[:, 1]
        return values

    def explain(self, X: pd.DataFrame | np.ndarray, top_k: int = 5) -> pd.DataFrame:
        if self.model is None:
            raise RuntimeError("Detector is not trained")
        frame = self._as_frame(X)
        shap_values = self._shap_matrix(frame)
        importance = np.abs(shap_values).mean(axis=0)
        top_idx = np.argsort(importance)[-top_k:][::-1]
        return pd.DataFrame(
            {
                "feature": [self.feature_names[i] for i in top_idx],
                "importance": importance[top_idx],
                "shap_value": shap_values[:, top_idx].mean(axis=0),
            }
        )

    def explain_row(self, X: pd.DataFrame | np.ndarray, top_k: int = 5) -> pd.DataFrame:
        frame = self._as_frame(X).iloc[[0]]
        values = self._shap_matrix(frame).reshape(-1)
        top_idx = np.argsort(np.abs(values))[-top_k:][::-1]
        return pd.DataFrame(
            {
                "feature": [self.feature_names[i] for i in top_idx],
                "importance": np.abs(values)[top_idx],
                "shap_value": values[top_idx],
            }
        )

    def _as_frame(self, X: pd.DataFrame | np.ndarray) -> pd.DataFrame:
        if isinstance(X, pd.DataFrame):
            X = ensure_narrative(X)
            return X[self.feature_names].astype(float)
        arr = np.asarray(X, dtype=float)
        if arr.ndim == 1:
            arr = arr.reshape(1, -1)
        return pd.DataFrame(arr, columns=self.feature_names)

    def save(self, path: Path | None = None) -> Path:
        path = path or DETECTOR_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(
            {
                "model": self.model,
                "threshold": self.threshold,
                "feature_names": self.feature_names,
                "metrics": self.metrics,
                "backend": self.backend,
                "feature_means": self._feature_means,
            },
            path,
        )
        return path

    @classmethod
    def load(cls, path: Path | None = None) -> "FraudDetector":
        path = path or DETECTOR_PATH
        blob = joblib.load(path)
        det = cls()
        det.model = blob["model"]
        det.threshold = float(blob["threshold"])
        det.feature_names = list(blob["feature_names"])
        det.metrics = dict(blob.get("metrics") or {})
        det.backend = blob.get("backend", "xgboost" if HAS_XGBOOST else "hist_gbdt")
        det._feature_means = blob.get("feature_means")
        return det


def train_and_save(X: pd.DataFrame, y: pd.Series, path: Path | None = None) -> FraudDetector:
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    detector = FraudDetector()
    detector.train(X, y)
    detector.save(path)
    return detector


__all__ = ["FraudDetector", "best_threshold", "train_and_save"]
