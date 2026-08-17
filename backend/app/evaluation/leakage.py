"""Blue Team must not train on attack identity columns."""

from __future__ import annotations

from app.core.config import FEATURE_COLUMNS, FEATURE_COLUMNS_V011, FEATURE_COLUMNS_V012, FEATURE_COLUMNS_V020, LEAKAGE_FORBIDDEN


def leakage_paths(columns: list[str] | None = None) -> list[str]:
    cols = list(columns or FEATURE_COLUMNS)
    return [name for name in LEAKAGE_FORBIDDEN if name in cols]


def assert_no_leakage() -> None:
    for cols in (FEATURE_COLUMNS, FEATURE_COLUMNS_V011, FEATURE_COLUMNS_V012, FEATURE_COLUMNS_V020):
        found = leakage_paths(list(cols))
        if found:
            raise AssertionError(f"label leakage in feature columns: {found}")
