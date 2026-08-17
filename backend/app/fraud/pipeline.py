"""Train/test split, model 0A/0B, metrics. No attack_family in features."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from app.core.config import FEATURE_COLUMNS, MODELS_DIR, RANDOM_STATE, ensure_dirs
from app.data.ingest import attach_merchant_risk

try:
    import lightgbm as lgb

    HAS_LGB = True
except Exception:  # noqa: BLE001
    lgb = None
    HAS_LGB = False


def feature_matrix(df: pd.DataFrame) -> pd.DataFrame:
    work = df.copy()
    for col in FEATURE_COLUMNS:
        if col not in work.columns:
            work[col] = 0.0
    return work[FEATURE_COLUMNS].apply(pd.to_numeric, errors="coerce").fillna(0.0).astype(float)


def _fpr(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    neg = y_true == 0
    if neg.sum() == 0:
        return 0.0
    return float(((y_pred == 1) & neg).sum() / neg.sum())


def compute_metrics(y_true: np.ndarray, proba: np.ndarray, threshold: float = 0.5) -> dict[str, float]:
    pred = (proba >= threshold).astype(int)
    return {
        "precision": float(precision_score(y_true, pred, zero_division=0)),
        "recall": float(recall_score(y_true, pred, zero_division=0)),
        "f1": float(f1_score(y_true, pred, zero_division=0)),
        "pr_auc": float(average_precision_score(y_true, proba)) if y_true.sum() else 0.0,
        "roc_auc": float(roc_auc_score(y_true, proba)) if len(np.unique(y_true)) > 1 else 0.0,
        "fpr": _fpr(y_true, pred),
        "threshold": float(threshold),
        "n": int(len(y_true)),
        "n_pos": int(y_true.sum()),
    }


def prepare_split(
    payments: pd.DataFrame,
    attacks: pd.DataFrame | None = None,
    seed: int = RANDOM_STATE,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    base = payments.copy()
    train_idx, test_idx = train_test_split(
        np.arange(len(base)),
        test_size=0.2,
        random_state=seed,
        stratify=base["fraud_label"] if base["fraud_label"].nunique() > 1 else None,
    )
    train = attach_merchant_risk(base.iloc[train_idx], base.iloc[train_idx])
    test = attach_merchant_risk(base.iloc[train_idx], base.iloc[test_idx])
    if attacks is not None and len(attacks):
        atk = attach_merchant_risk(train, attacks)
        mid = len(atk) // 2
        train = pd.concat([train, atk.iloc[:mid]], ignore_index=True)
        test = pd.concat([test, atk.iloc[mid:]], ignore_index=True)
    return train.reset_index(drop=True), test.reset_index(drop=True)


def train_logreg(X: pd.DataFrame, y: pd.Series) -> Pipeline:
    pipe = Pipeline(
        [
            ("scaler", StandardScaler()),
            ("clf", LogisticRegression(max_iter=400, class_weight="balanced", random_state=RANDOM_STATE)),
        ]
    )
    pipe.fit(X, y)
    return pipe


def train_lightgbm(X: pd.DataFrame, y: pd.Series):
    if not HAS_LGB:
        from sklearn.ensemble import HistGradientBoostingClassifier

        model = HistGradientBoostingClassifier(max_depth=6, max_iter=120, random_state=RANDOM_STATE)
        model.fit(X, y)
        return model
    pos = max(int((y == 1).sum()), 1)
    neg = max(int((y == 0).sum()), 1)
    model = lgb.LGBMClassifier(
        n_estimators=160,
        learning_rate=0.08,
        num_leaves=31,
        subsample=0.8,
        colsample_bytree=0.8,
        scale_pos_weight=neg / pos,
        random_state=RANDOM_STATE,
        verbosity=-1,
    )
    model.fit(X, y)
    return model


def predict_proba(model: Any, X: pd.DataFrame) -> np.ndarray:
    proba = model.predict_proba(X)
    if proba.ndim == 2:
        return proba[:, 1]
    return np.asarray(proba, dtype=float)


class BlueTeam:
    def __init__(self) -> None:
        self.logreg = None
        self.lgbm = None
        self.metrics: dict[str, Any] = {}
        self.feature_names = list(FEATURE_COLUMNS)

    def train(self, train: pd.DataFrame, test: pd.DataFrame) -> dict[str, Any]:
        Xtr, ytr = feature_matrix(train), train["fraud_label"].astype(int)
        Xte, yte = feature_matrix(test), test["fraud_label"].astype(int)
        self.logreg = train_logreg(Xtr, ytr)
        self.lgbm = train_lightgbm(Xtr, ytr)
        p_a = predict_proba(self.logreg, Xte)
        p_b = predict_proba(self.lgbm, Xte)
        self.metrics = {
            "logreg": compute_metrics(yte.to_numpy(), p_a),
            "lightgbm": compute_metrics(yte.to_numpy(), p_b),
            "backend": "lightgbm" if HAS_LGB else "hist_gbdt",
        }
        self.metrics["feature_importance"] = [
            {"feature": name, "importance": value} for name, value in self.importance_pairs(Xte, yte)
        ]
        return self.metrics

    def importance_pairs(
        self,
        X: pd.DataFrame | None = None,
        y: pd.Series | np.ndarray | None = None,
    ) -> list[tuple[str, float]]:
        """Native split gain, permutation on HistGB, then |logreg| coefficients."""
        names = list(self.feature_names)
        raw = self._native_importance()
        if raw is None and X is not None and y is not None and self.lgbm is not None:
            raw = self._permutation_importance(X, y)
        if raw is None:
            raw = self._logreg_importance()
        if raw is None:
            return [(name, 0.0) for name in names]
        raw = np.nan_to_num(np.clip(np.asarray(raw, dtype=float), 0.0, None), nan=0.0)
        if float(raw.sum()) <= 0 or int((raw > 0).sum()) < 3:
            fallback = self._logreg_importance()
            if fallback is not None:
                raw = np.nan_to_num(np.abs(np.asarray(fallback, dtype=float)), nan=0.0)
        total = float(raw.sum()) or 1.0
        return sorted(zip(names, (raw / total).tolist()), key=lambda item: -item[1])

    def _native_importance(self) -> np.ndarray | None:
        model = self.lgbm
        if model is None or not hasattr(model, "feature_importances_"):
            return None
        values = np.asarray(model.feature_importances_, dtype=float)
        if values.size != len(self.feature_names) or float(np.abs(values).sum()) <= 0:
            return None
        return values

    def _permutation_importance(self, X: pd.DataFrame, y: pd.Series | np.ndarray) -> np.ndarray | None:
        from sklearn.inspection import permutation_importance

        n = min(len(X), 400)
        if n < 20:
            return None
        ys = y.iloc[:n] if hasattr(y, "iloc") else np.asarray(y)[:n]
        try:
            result = permutation_importance(
                self.lgbm,
                X.iloc[:n],
                ys,
                n_repeats=3,
                random_state=RANDOM_STATE,
                n_jobs=1,
            )
        except Exception:  # noqa: BLE001
            return None
        return np.asarray(result.importances_mean, dtype=float)

    def _logreg_importance(self) -> np.ndarray | None:
        if self.logreg is None:
            return None
        clf = getattr(self.logreg, "named_steps", {}).get("clf")
        if clf is None or not hasattr(clf, "coef_"):
            return None
        return np.abs(np.asarray(clf.coef_, dtype=float).reshape(-1))

    def score(self, df: pd.DataFrame) -> np.ndarray:
        if self.lgbm is None:
            raise RuntimeError("Model not trained")
        return predict_proba(self.lgbm, feature_matrix(df))

    def save(self) -> Path:
        ensure_dirs()
        path = MODELS_DIR / "blue_team.joblib"
        joblib.dump({"logreg": self.logreg, "lgbm": self.lgbm, "metrics": self.metrics}, path)
        (MODELS_DIR / "metrics.json").write_text(json.dumps(self.metrics, indent=2))
        return path

    @classmethod
    def load(cls, path: Path | None = None) -> "BlueTeam":
        blob = joblib.load(path or MODELS_DIR / "blue_team.joblib")
        team = cls()
        team.logreg = blob["logreg"]
        team.lgbm = blob["lgbm"]
        team.metrics = blob.get("metrics") or {}
        return team
