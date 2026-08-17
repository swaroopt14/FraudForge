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

from app.core.config import (
    FEATURE_COLUMNS,
    FEATURE_COLUMNS_V011,
    FEATURE_COLUMNS_V012,
    FEATURE_COLUMNS_V020,
    MODELS_DIR,
    RANDOM_STATE,
    ensure_dirs,
)
from app.data.ingest import attach_merchant_risk

try:
    import lightgbm as lgb

    HAS_LGB = True
except Exception:  # noqa: BLE001
    lgb = None
    HAS_LGB = False


def feature_matrix(df: pd.DataFrame, columns: list[str] | None = None) -> pd.DataFrame:
    cols = list(columns or FEATURE_COLUMNS)
    work = df.copy()
    for col in cols:
        if col not in work.columns:
            work[col] = 0.0
    return work[cols].apply(pd.to_numeric, errors="coerce").fillna(0.0).astype(float)


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


def prepare_split_balanced(
    payments: pd.DataFrame,
    attacks: pd.DataFrame | None = None,
    seed: int = RANDOM_STATE,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """IEEE 80/20, then 50/50 *within each attack family* so every family is in train and test."""
    train, test = prepare_split(payments, attacks=None, seed=seed)
    if attacks is None or not len(attacks):
        return train, test
    atk = attach_merchant_risk(train, attacks)
    parts_tr: list[pd.DataFrame] = []
    parts_te: list[pd.DataFrame] = []
    family_col = "attack_family" if "attack_family" in atk.columns else None
    if family_col is None:
        mid = len(atk) // 2
        train = pd.concat([train, atk.iloc[:mid]], ignore_index=True)
        test = pd.concat([test, atk.iloc[mid:]], ignore_index=True)
        return train.reset_index(drop=True), test.reset_index(drop=True)
    for _family, group in atk.groupby(family_col, sort=False):
        shuffled = group.sample(frac=1.0, random_state=seed)
        mid = max(1, len(shuffled) // 2)
        if mid >= len(shuffled):
            mid = max(len(shuffled) - 1, 1)
        parts_tr.append(shuffled.iloc[:mid])
        parts_te.append(shuffled.iloc[mid:] if mid < len(shuffled) else shuffled.iloc[-1:])
    train = pd.concat([train, *parts_tr], ignore_index=True)
    test = pd.concat([test, *parts_te], ignore_index=True)
    return train.reset_index(drop=True), test.reset_index(drop=True)


def _uses_family_weights(model_id: str) -> bool:
    mid = str(model_id or "")
    if mid.startswith("BLUE-0.2"):
        return True
    return mid.startswith("BLUE-0.1.") and not mid.startswith("BLUE-0.1.0")


def family_balanced_weights(frame: pd.DataFrame) -> np.ndarray:
    """Keep quiet families from being drowned by amount-loud overlays."""
    weights = np.ones(len(frame), dtype=float)
    if "attack_family" not in frame.columns or "fraud_label" not in frame.columns:
        return weights
    pos = frame["fraud_label"].astype(int).to_numpy() == 1
    families = frame["attack_family"].fillna("").astype(str).to_numpy()
    labeled = pos & (families != "") & (families != "nan")
    if not labeled.any():
        return weights
    counts: dict[str, int] = {}
    for family in families[labeled]:
        counts[family] = counts.get(family, 0) + 1
    target = float(max(counts.values()))
    boost = {"beneficiary_anomaly": 2.4, "mule_network": 2.0, "geo_anomaly": 1.3, "intent_mismatch": 1.3}
    scale = {family: (target / max(n, 1)) * boost.get(family, 1.0) for family, n in counts.items()}
    for i, (is_pos, family) in enumerate(zip(labeled, families)):
        if is_pos:
            weights[i] = scale.get(family, 1.0)
    return weights


def train_logreg(X: pd.DataFrame, y: pd.Series) -> Pipeline:
    pipe = Pipeline(
        [
            ("scaler", StandardScaler()),
            ("clf", LogisticRegression(max_iter=400, class_weight="balanced", random_state=RANDOM_STATE)),
        ]
    )
    pipe.fit(X, y)
    return pipe


def train_lightgbm(X: pd.DataFrame, y: pd.Series, sample_weight: np.ndarray | None = None):
    if not HAS_LGB:
        from sklearn.ensemble import HistGradientBoostingClassifier

        model = HistGradientBoostingClassifier(max_depth=6, max_iter=120, random_state=RANDOM_STATE)
        model.fit(X, y, sample_weight=sample_weight)
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
    model.fit(X, y, sample_weight=sample_weight)
    return model


def predict_proba(model: Any, X: pd.DataFrame) -> np.ndarray:
    proba = model.predict_proba(X)
    if proba.ndim == 2:
        return proba[:, 1]
    return np.asarray(proba, dtype=float)


class BlueTeam:
    def __init__(self, feature_names: list[str] | None = None, model_id: str = "BLUE-0.1.0") -> None:
        self.logreg = None
        self.lgbm = None
        self.metrics: dict[str, Any] = {}
        self.feature_names = list(feature_names or FEATURE_COLUMNS)
        self.model_id = model_id
        self.calibrator = None
        names = list(self.feature_names)
        if names == list(FEATURE_COLUMNS_V020):
            self.feature_version = "BLUE-FEAT-0.2.0"
        elif names == list(FEATURE_COLUMNS_V012):
            self.feature_version = "BLUE-FEAT-0.1.2"
        elif names == list(FEATURE_COLUMNS_V011):
            self.feature_version = "BLUE-FEAT-0.1.1"
        else:
            self.feature_version = "BLUE-FEAT-0.1.0"

    def train(self, train: pd.DataFrame, test: pd.DataFrame, *, calibrate: bool = False) -> dict[str, Any]:
        fit_frame, calib_frame = train, None
        if calibrate and len(train) >= 80 and train["fraud_label"].nunique() > 1:
            try:
                fit_idx, cal_idx = train_test_split(
                    np.arange(len(train)),
                    test_size=0.2,
                    random_state=RANDOM_STATE,
                    stratify=train["fraud_label"],
                )
            except ValueError:
                fit_idx, cal_idx = train_test_split(
                    np.arange(len(train)),
                    test_size=0.2,
                    random_state=RANDOM_STATE,
                )
            fit_frame = train.iloc[fit_idx]
            calib_frame = train.iloc[cal_idx]
        Xtr, ytr = feature_matrix(fit_frame, self.feature_names), fit_frame["fraud_label"].astype(int)
        Xte, yte = feature_matrix(test, self.feature_names), test["fraud_label"].astype(int)
        weights = family_balanced_weights(fit_frame) if _uses_family_weights(self.model_id) else None
        self.logreg = train_logreg(Xtr, ytr)
        self.lgbm = train_lightgbm(Xtr, ytr, sample_weight=weights)
        if calibrate and calib_frame is not None and len(calib_frame):
            from app.blue_team.classifiers.calibration import ProbabilityCalibrator

            raw = predict_proba(self.lgbm, feature_matrix(calib_frame, self.feature_names))
            self.calibrator = ProbabilityCalibrator().fit(calib_frame["fraud_label"].to_numpy(), raw)
        p_a = self._maybe_calibrate(predict_proba(self.logreg, Xte))
        p_b = self._maybe_calibrate(predict_proba(self.lgbm, Xte))
        self.metrics = {
            "logreg": compute_metrics(yte.to_numpy(), p_a),
            "lightgbm": compute_metrics(yte.to_numpy(), p_b),
            "backend": "lightgbm" if HAS_LGB else "hist_gbdt",
            "model_id": self.model_id,
            "feature_version": self.feature_version,
            "n_features": len(self.feature_names),
            "calibrated": bool(self.calibrator and getattr(self.calibrator, "fitted", False)),
        }
        if self.calibrator is not None:
            self.metrics["calibration"] = {
                "brier_before": getattr(self.calibrator, "brier_before", None),
                "brier_after": getattr(self.calibrator, "brier_after", None),
            }
        self.metrics["feature_importance"] = [
            {"feature": name, "importance": value} for name, value in self.importance_pairs(Xte, yte)
        ]
        return self.metrics

    def _maybe_calibrate(self, proba: np.ndarray) -> np.ndarray:
        if self.calibrator is not None and getattr(self.calibrator, "fitted", False):
            return self.calibrator.transform(proba)
        return proba

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
        work = df
        if list(self.feature_names) == list(FEATURE_COLUMNS_V020):
            from app.blue_team.context import ensure_p2

            work = ensure_p2(df)
        return self._maybe_calibrate(predict_proba(self.lgbm, feature_matrix(work, self.feature_names)))

    def save(self, path: Path | None = None) -> Path:
        ensure_dirs()
        dest = Path(path) if path is not None else MODELS_DIR / "blue_team.joblib"
        dest.parent.mkdir(parents=True, exist_ok=True)
        blob = {
            "logreg": self.logreg,
            "lgbm": self.lgbm,
            "metrics": self.metrics,
            "feature_names": self.feature_names,
            "model_id": self.model_id,
            "calibrator": self.calibrator,
            "feature_version": self.feature_version,
        }
        joblib.dump(blob, dest)
        (dest.parent / "metrics.json").write_text(json.dumps(self.metrics, indent=2, default=str))
        (dest.parent / "VERSION.json").write_text(
            json.dumps(
                {
                    "model_version": self.model_id,
                    "feature_version": self.feature_version,
                    "n_features": len(self.feature_names),
                    "calibrated": bool(self.calibrator and getattr(self.calibrator, "fitted", False)),
                },
                indent=2,
            )
        )
        default_path = MODELS_DIR / "blue_team.joblib"
        if dest.resolve() == default_path.resolve():
            (MODELS_DIR / "metrics.json").write_text(json.dumps(self.metrics, indent=2, default=str))
        return dest

    @classmethod
    def load(cls, path: Path | None = None) -> "BlueTeam":
        blob = joblib.load(path or MODELS_DIR / "blue_team.joblib")
        names = list(blob.get("feature_names") or FEATURE_COLUMNS)
        team = cls(feature_names=names, model_id=str(blob.get("model_id") or "BLUE-0.1.0"))
        team.logreg = blob["logreg"]
        team.lgbm = blob["lgbm"]
        team.metrics = blob.get("metrics") or {}
        team.calibrator = blob.get("calibrator")
        team.feature_version = str(blob.get("feature_version") or team.feature_version)
        return team

    def version(self) -> str:
        backend = str(self.metrics.get("backend") or ("lightgbm" if HAS_LGB else "hist_gbdt"))
        pr = (self.metrics.get("lightgbm") or {}).get("pr_auc")
        tag = f"-prauc{float(pr):.3f}" if pr is not None else ""
        return f"{self.model_id}-{backend}{tag}"
