"""Versioned model registry. Never overwrite a frozen artifact."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from app.core.config import MODELS_DIR

REGISTRY_PATH = MODELS_DIR / "registry.json"
FROZEN_BLUE = MODELS_DIR / "BLUE-0.1.0" / "blue_team.joblib"
FROZEN_BLUE_SHA256 = "66dbe604ad79405a32a320a8e4809d4c0a5a1c98880b1910d834b8bab93c820c"


def load_registry() -> dict[str, Any]:
    if not REGISTRY_PATH.exists():
        return {}
    return json.loads(REGISTRY_PATH.read_text())


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 16), b""):
            digest.update(chunk)
    return digest.hexdigest()


def assert_frozen_blue() -> None:
    if not FROZEN_BLUE.exists():
        raise FileNotFoundError(f"frozen detector missing: {FROZEN_BLUE}")
    found = sha256_file(FROZEN_BLUE)
    if found != FROZEN_BLUE_SHA256:
        raise AssertionError(
            f"BLUE-0.1.0 was overwritten. expected {FROZEN_BLUE_SHA256}, found {found}"
        )


def team_versions() -> dict[str, Any]:
    reg = load_registry()
    return {
        "red_team": (reg.get("red_team") or {}),
        "blue_team": (reg.get("blue_team") or {}),
        "feature_version": reg.get("feature_version"),
        "frozen_blue_present": FROZEN_BLUE.exists(),
    }
