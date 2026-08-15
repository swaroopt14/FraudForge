"""Shared pytest fixtures. Backend is on sys.path via pytest.ini pythonpath."""

from __future__ import annotations

from pathlib import Path

import pytest

from config import DETECTOR_PATH


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def detector_available() -> bool:
    return DETECTOR_PATH.exists()
