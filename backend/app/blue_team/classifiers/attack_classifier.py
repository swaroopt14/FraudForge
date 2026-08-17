"""Attack family classifier. Separate from BlueFraudDetector. Unknown → UNKNOWN/EMERGING."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.preprocessing import LabelEncoder

import hashlib

from app.core.config import FEATURE_COLUMNS, FEATURE_COLUMNS_V011, FEATURE_COLUMNS_V012, FEATURE_COLUMNS_V020, MODELS_DIR, ensure_dirs
from app.evaluation.leakage import assert_no_leakage
from app.fraud.pipeline import feature_matrix

VERSION = "BLUE-CLS-0.1.0"
VERSION_V011 = "BLUE-CLS-0.1.1"
VERSION_V012 = "BLUE-CLS-0.1.2"
VERSION_V020 = "BLUE-CLS-0.2.0"
ARTIFACT = MODELS_DIR / VERSION / "attack_classifier.joblib"
ARTIFACT_V011 = MODELS_DIR / VERSION_V011 / "attack_classifier.joblib"
ARTIFACT_V012 = MODELS_DIR / VERSION_V012 / "attack_classifier.joblib"
ARTIFACT_V020 = MODELS_DIR / VERSION_V020 / "attack_classifier.joblib"
UNKNOWN = "UNKNOWN"
EMERGING = "EMERGING"
MIN_PER_CLASS = 12


class BlueAttackClassifier:
    def __init__(self, feature_names: list[str] | None = None, version: str = VERSION) -> None:
        self.model: HistGradientBoostingClassifier | None = None
        self.variant_model: HistGradientBoostingClassifier | None = None
        self.encoder = LabelEncoder()
        self.variant_encoder = LabelEncoder()
        self.classes_: list[str] = []
        self.variant_classes_: list[str] = []
        self.version = version
        self.feature_names = list(feature_names or FEATURE_COLUMNS)
        self.fitted = False
        self.variant_fitted = False

    def _frame(self, frame: pd.DataFrame) -> pd.DataFrame:
        if list(self.feature_names) == list(FEATURE_COLUMNS_V020):
            from app.blue_team.context import ensure_p2

            return ensure_p2(frame)
        return frame

    def fit(self, frame: pd.DataFrame, labels: pd.Series, variants: pd.Series | None = None) -> "BlueAttackClassifier":
        assert_no_leakage()
        x = feature_matrix(self._frame(frame), self.feature_names)
        y = labels.astype(str)
        counts = y.value_counts()
        keep = [c for c, n in counts.items() if int(n) >= MIN_PER_CLASS and c not in {"", "nan"}]
        mask = y.isin(keep)
        if mask.sum() < 20 or len(keep) < 2:
            self.fitted = False
            return self
        self.encoder.fit(y[mask])
        self.classes_ = list(self.encoder.classes_)
        self.model = HistGradientBoostingClassifier(max_depth=4, max_iter=60, random_state=7)
        self.model.fit(x.loc[mask], self.encoder.transform(y[mask]))
        self.fitted = True
        if variants is not None:
            v = variants.astype(str)
            v_counts = v.value_counts()
            v_keep = [c for c, n in v_counts.items() if int(n) >= MIN_PER_CLASS and c not in {"", "nan", "legit"}]
            v_mask = v.isin(v_keep)
            if v_mask.sum() >= 20 and len(v_keep) >= 2:
                self.variant_encoder.fit(v[v_mask])
                self.variant_classes_ = list(self.variant_encoder.classes_)
                self.variant_model = HistGradientBoostingClassifier(max_depth=4, max_iter=80, random_state=7)
                self.variant_model.fit(x.loc[v_mask], self.variant_encoder.transform(v[v_mask]))
                self.variant_fitted = True
        return self

    def predict(self, frame: pd.DataFrame, fraud_probability: np.ndarray | None = None) -> list[dict[str, Any]]:
        n = len(frame)
        if not self.fitted or self.model is None:
            return [{"family": UNKNOWN, "variant": None, "confidence": 0.0, "status": EMERGING} for _ in range(n)]
        x = feature_matrix(self._frame(frame), self.feature_names)
        proba = self.model.predict_proba(x)
        idx = np.argmax(proba, axis=1)
        variant_idx = None
        variant_proba = None
        if self.variant_fitted and self.variant_model is not None:
            variant_proba = self.variant_model.predict_proba(x)
            variant_idx = np.argmax(variant_proba, axis=1)
        out = []
        for i, j in enumerate(idx):
            conf = float(proba[i, j])
            family = str(self.classes_[int(j)])
            p_fraud = None if fraud_probability is None else float(fraud_probability[i])
            variant = None
            if variant_idx is not None and variant_proba is not None:
                v_conf = float(variant_proba[i, int(variant_idx[i])])
                if v_conf >= 0.35:
                    variant = str(self.variant_classes_[int(variant_idx[i])])
            if conf < 0.35 or family == "legit":
                status = EMERGING if (p_fraud is not None and p_fraud >= 0.5) else UNKNOWN
                family_out = UNKNOWN if status == UNKNOWN else EMERGING
                out.append({"family": family_out, "variant": None, "confidence": conf, "status": status})
            else:
                out.append({"family": family, "variant": variant, "confidence": conf, "status": "known"})
        return out

    def save(self, path: Path | None = None) -> Path:
        ensure_dirs()
        dest = path or ARTIFACT
        dest.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(
            {
                "model": self.model,
                "variant_model": self.variant_model,
                "encoder": self.encoder,
                "variant_encoder": self.variant_encoder,
                "classes": self.classes_,
                "variant_classes": self.variant_classes_,
                "fitted": self.fitted,
                "variant_fitted": self.variant_fitted,
                "version": self.version,
                "feature_names": self.feature_names,
            },
            dest,
        )
        (dest.parent / "VERSION.json").write_text(
            json.dumps(
                {
                    "model_version": self.version,
                    "fitted": self.fitted,
                    "classes": self.classes_,
                    "variant_classes": self.variant_classes_,
                },
                indent=2,
            )
        )
        return dest

    @classmethod
    def load(cls, path: Path | None = None) -> "BlueAttackClassifier":
        inst = cls()
        src = path or ARTIFACT
        if not src.exists():
            return inst
        blob = joblib.load(src)
        inst.model = blob.get("model")
        inst.variant_model = blob.get("variant_model")
        inst.encoder = blob.get("encoder") or LabelEncoder()
        inst.variant_encoder = blob.get("variant_encoder") or LabelEncoder()
        inst.classes_ = list(blob.get("classes") or [])
        inst.variant_classes_ = list(blob.get("variant_classes") or [])
        inst.fitted = bool(blob.get("fitted"))
        inst.variant_fitted = bool(blob.get("variant_fitted"))
        inst.version = str(blob.get("version") or inst.version)
        inst.feature_names = list(blob.get("feature_names") or FEATURE_COLUMNS)
        return inst


def train_from_overlays(payments: pd.DataFrame, registry, n_each: int = 24) -> BlueAttackClassifier:
    """Train identification only. Never writes BLUE-0.1.0."""
    from app.redteam.difficulty import resolve_mutation
    from app.redteam.mutations import apply_mutation
    from app.simulation.legit import fit_profiles, generate_legitimate

    profiles = fit_profiles(payments)
    from app.data.history import CorpusHistory

    history = CorpusHistory.from_payments(payments)
    frames = []
    labels = []
    legit = generate_legitimate(profiles, max(40, n_each), seed=3, history=history, source=payments)
    frames.append(legit)
    labels.extend(["legit"] * len(legit))
    for threat in registry.list():
        mutation = resolve_mutation(registry, threat.attack_id, "MEDIUM", None)
        seed = int(hashlib.md5(threat.attack_id.encode()).hexdigest()[:8], 16)
        base = generate_legitimate(profiles, n_each, seed=seed % 10_000, history=history, source=payments)
        rng = np.random.default_rng(seed)
        rows = history.attach(apply_mutation(base, mutation, rng, threat.family), refresh_concentration=False)
        frames.append(rows)
        labels.extend([threat.family] * len(rows))
    data = pd.concat(frames, ignore_index=True)
    clf = BlueAttackClassifier().fit(data, pd.Series(labels))
    clf.save()
    return clf


def train_from_variants(payments: pd.DataFrame, registry, n_each: int = 24) -> BlueAttackClassifier:
    """Family + variant identification on v0.1.1 features. Never writes BLUE-0.1.0."""
    from app.redteam.difficulty import resolve_mutation
    from app.redteam.mutations import apply_mutation
    from app.simulation.legit import fit_profiles, generate_legitimate

    profiles = fit_profiles(payments)
    from app.data.history import CorpusHistory

    history = CorpusHistory.from_payments(payments)
    frames = []
    labels: list[str] = []
    variant_ids: list[str] = []
    legit = generate_legitimate(profiles, max(40, n_each), seed=3, history=history, source=payments)
    frames.append(legit)
    labels.extend(["legit"] * len(legit))
    variant_ids.extend(["legit"] * len(legit))
    for i, (threat, variant) in enumerate(registry.all_variants()):
        mutation = resolve_mutation(registry, threat.attack_id, "MEDIUM", variant.id)
        seed = int(hashlib.md5(f"{threat.attack_id}:{variant.id}".encode()).hexdigest()[:8], 16)
        base = generate_legitimate(profiles, n_each, seed=(seed + i) % 10_000, history=history, source=payments)
        rng = np.random.default_rng(seed)
        rows = history.attach(apply_mutation(base, mutation, rng, threat.family), refresh_concentration=False)
        frames.append(rows)
        labels.extend([threat.family] * len(rows))
        variant_ids.extend([variant.id] * len(rows))
    data = pd.concat(frames, ignore_index=True)
    clf = BlueAttackClassifier(feature_names=list(FEATURE_COLUMNS_V012), version=VERSION_V012)
    clf.fit(data, pd.Series(labels), pd.Series(variant_ids))
    clf.save(ARTIFACT_V012)
    return clf


def train_from_variants_v020(payments: pd.DataFrame, registry, n_each: int = 24) -> BlueAttackClassifier:
    """Family + variant identification on P2 graph features. Never writes BLUE-0.1.0."""
    from app.blue_team.context import attach_p2_features
    from app.redteam.difficulty import resolve_mutation
    from app.redteam.mutations import apply_mutation
    from app.simulation.legit import fit_profiles, generate_legitimate

    profiles = fit_profiles(payments)
    from app.data.history import CorpusHistory

    history = CorpusHistory.from_payments(payments)
    frames = []
    labels: list[str] = []
    variant_ids: list[str] = []
    legit = attach_p2_features(generate_legitimate(profiles, max(40, n_each), seed=3, history=history, source=payments))
    frames.append(legit)
    labels.extend(["legit"] * len(legit))
    variant_ids.extend(["legit"] * len(legit))
    for i, (threat, variant) in enumerate(registry.all_variants()):
        mutation = resolve_mutation(registry, threat.attack_id, "MEDIUM", variant.id)
        seed = int(hashlib.md5(f"{threat.attack_id}:{variant.id}".encode()).hexdigest()[:8], 16)
        base = generate_legitimate(profiles, n_each, seed=(seed + i) % 10_000, history=history, source=payments)
        rng = np.random.default_rng(seed)
        rows = attach_p2_features(history.attach(apply_mutation(base, mutation, rng, threat.family), refresh_concentration=False))
        frames.append(rows)
        labels.extend([threat.family] * len(rows))
        variant_ids.extend([variant.id] * len(rows))
    data = pd.concat(frames, ignore_index=True)
    clf = BlueAttackClassifier(feature_names=list(FEATURE_COLUMNS_V020), version=VERSION_V020)
    clf.fit(data, pd.Series(labels), pd.Series(variant_ids))
    clf.save(ARTIFACT_V020)
    return clf
