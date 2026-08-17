"""BlueFraudDetector — P(fraud) only. Default artifact is frozen BLUE-0.1.0."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from app.core.config import BLUE_MODEL_VERSION, FEATURE_COLUMNS, MODELS_DIR
from app.core.model_registry import FROZEN_BLUE, assert_frozen_blue
from app.evaluation.leakage import assert_no_leakage
from app.fraud.pipeline import BlueTeam, feature_matrix

VERSION = "BLUE-0.1.0"
V011 = MODELS_DIR / "BLUE-0.1.1" / "blue_team.joblib"
V012 = MODELS_DIR / "BLUE-0.1.2" / "blue_team.joblib"


class BlueFraudDetector:
    def __init__(self, team: BlueTeam | None = None) -> None:
        assert_no_leakage()
        self.team = team
        self.version = VERSION
        self.feature_names = list(FEATURE_COLUMNS)

    def load_frozen(self) -> "BlueFraudDetector":
        assert_frozen_blue()
        self.team = BlueTeam.load(FROZEN_BLUE)
        self.version = self.team.model_id
        self.feature_names = list(self.team.feature_names)
        return self

    def load_active(self) -> "BlueFraudDetector":
        """Default live detector is BLUE-0.1.2 when present. BLUE-0.1.0 stays frozen."""
        if BLUE_MODEL_VERSION.startswith("BLUE-0.1.0"):
            return self.load_frozen()
        if BLUE_MODEL_VERSION.startswith("BLUE-0.1.1") and V011.exists():
            self.team = BlueTeam.load(V011)
        elif V012.exists() and not BLUE_MODEL_VERSION.startswith("BLUE-0.1.0"):
            self.team = BlueTeam.load(V012)
        elif V011.exists() and BLUE_MODEL_VERSION.startswith("BLUE-0.1.1"):
            self.team = BlueTeam.load(V011)
        else:
            return self.load_frozen()
        self.version = self.team.model_id
        self.feature_names = list(self.team.feature_names)
        return self

    def score(self, df: pd.DataFrame):
        if self.team is None:
            raise RuntimeError("detector not loaded")
        frame = feature_matrix(df, self.team.feature_names)
        assert list(frame.columns) == list(self.team.feature_names)
        return self.team.score(df)

    def artifact(self) -> Path:
        if self.team is not None and str(self.team.model_id).startswith("BLUE-0.1.2"):
            return V012
        if self.team is not None and str(self.team.model_id).startswith("BLUE-0.1.1"):
            return V011
        return FROZEN_BLUE if FROZEN_BLUE.exists() else MODELS_DIR / "blue_team.joblib"
