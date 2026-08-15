"""Streamlit Cloud / single-process entrypoint."""

from __future__ import annotations

import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "backend"))
runpy.run_path(str(ROOT / "frontend" / "app.py"), run_name="__main__")
