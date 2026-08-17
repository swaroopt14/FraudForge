"""BLUE-FRAUD-0.2.0 and BLUE-ATTACK-CLS-0.2.0. Labels never enter X."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import LabelEncoder, StandardScaler

from app.blue_team.features import feature_matrix_v020
from app.core.config import FEATURE_COLUMNS_V020, LEAKAGE_COLUMNS, MODELS_DIR, RANDOM_STATE, ensure_dirs
from app.fraud.pipeline import compute_metrics, predict_proba, train_lightgbm

FRAUD_MODEL_ID = "BLUE-FRAUD-0.2.0"
CLS_MODEL_ID = "BLUE-ATTACK-CLS-0.2.0"
P0_MODEL_ID = "BLUE-0.1.0"


def _assert_no_leakage(columns: list[str]) -> None:
    leaked = [c for c in columns if c in LEAKAGE_COLUMNS]
    if leaked:
        raise RuntimeError(f"refusing to train with leakage columns: {leaked}")


class BlueTeamV2:
    def __init__(self) -> None:
        self.fraud_model = None
        self.classifier = None
        self.label_encoder: LabelEncoder | None = None
        self.metrics: dict[str, Any] = {"model_id": FRAUD_MODEL_ID, "classifier_id": CLS_MODEL_ID}
        self.feature_names = list(FEATURE_COLUMNS_V020)

    def train(self, train: pd.DataFrame, test: pd.DataFrame) -> dict[str, Any]:
        _assert_no_leakage(self.feature_names)
        Xtr = feature_matrix_v020(train)
        Xte = feature_matrix_v020(test)
        _assert_no_leakage(list(Xtr.columns))
        ytr = train["fraud_label"].astype(int)
        yte = test["fraud_label"].astype(int)
        self.fraud_model = train_lightgbm(Xtr, ytr)
        p = predict_proba(self.fraud_model, Xte)
        self.metrics["lightgbm"] = compute_metrics(yte.to_numpy(), p)
        self.metrics["backend"] = "lightgbm"
        self._train_classifier(train, test)
        return self.metrics

    def _train_classifier(self, train: pd.DataFrame, test: pd.DataFrame) -> None:
        fam_tr = train["attack_family"].fillna("").astype(str).replace({"": "none", "nan": "none"})
        fam_te = test["attack_family"].fillna("").astype(str).replace({"": "none", "nan": "none"})
        fam_tr = np.where(train["fraud_label"].astype(int) == 0, "none", fam_tr)
        fam_te = np.where(test["fraud_label"].astype(int) == 0, "none", fam_te)
        enc = LabelEncoder()
        ytr = enc.fit_transform(fam_tr)
        self.label_encoder = enc
        Xtr = feature_matrix_v020(train)
        Xte = feature_matrix_v020(test)
        try:
            import lightgbm as lgb

            clf = lgb.LGBMClassifier(
                n_estimators=120,
                learning_rate=0.08,
                num_leaves=24,
                random_state=RANDOM_STATE,
                verbosity=-1,
            )
            clf.fit(Xtr, ytr)
            self.classifier = clf
        except Exception:  # noqa: BLE001
            pipe = Pipeline(
                [
                    ("scaler", StandardScaler()),
                    ("clf", LogisticRegression(max_iter=400, random_state=RANDOM_STATE)),
                ]
            )
            pipe.fit(Xtr, ytr)
            self.classifier = pipe
        pred = self.classifier.predict(Xte)
        known = np.isin(fam_te, enc.classes_)
        if known.any():
            acc = float((pred[known] == enc.transform(fam_te[known])).mean())
        else:
            acc = 0.0
        self.metrics["classifier_accuracy"] = acc

    def score(self, df: pd.DataFrame) -> np.ndarray:
        if self.fraud_model is None:
            raise RuntimeError("P2 fraud model not trained")
        return predict_proba(self.fraud_model, feature_matrix_v020(df))

    def classify(self, df: pd.DataFrame) -> list[dict[str, Any]]:
        X = feature_matrix_v020(df)
        if self.classifier is None or self.label_encoder is None:
            return [{"family": "unknown", "confidence": 0.0} for _ in range(len(X))]
        if hasattr(self.classifier, "predict_proba"):
            proba = np.asarray(self.classifier.predict_proba(X))
            idx = proba.argmax(axis=1)
            conf = proba.max(axis=1)
        else:
            idx = np.asarray(self.classifier.predict(X))
            conf = np.ones(len(idx), dtype=float)
        labels = self.label_encoder.inverse_transform(idx)
        return [{"family": str(lab), "confidence": float(c)} for lab, c in zip(labels, conf)]

    def save(self) -> Path:
        ensure_dirs()
        path = MODELS_DIR / "blue_fraud_0_2_0.joblib"
        joblib.dump(
            {
                "fraud_model": self.fraud_model,
                "classifier": self.classifier,
                "label_encoder": self.label_encoder,
                "metrics": self.metrics,
                "feature_names": self.feature_names,
            },
            path,
        )
        (MODELS_DIR / "blue_0_2_0_metrics.json").write_text(json.dumps(self.metrics, indent=2, default=str))
        return path

    @classmethod
    def load(cls, path: Path | None = None) -> "BlueTeamV2":
        blob = joblib.load(path or MODELS_DIR / "blue_fraud_0_2_0.joblib")
        team = cls()
        team.fraud_model = blob["fraud_model"]
        team.classifier = blob.get("classifier")
        team.label_encoder = blob.get("label_encoder")
        team.metrics = blob.get("metrics") or team.metrics
        team.feature_names = list(blob.get("feature_names") or FEATURE_COLUMNS_V020)
        return team
