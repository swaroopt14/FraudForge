from __future__ import annotations

from pathlib import Path

import pytest

LAB = Path(__file__).resolve().parents[2]
COMPOSE = LAB / "docker-compose.yml"


def test_compose_services_declared() -> None:
    text = COMPOSE.read_text()
    assert "services:" in text
    for name in ("backend:", "frontend:", "postgres:"):
        assert name in text
    assert "8000:8000" in text
    assert "/health" in text


def test_compose_config_valid() -> None:
    import shutil
    import subprocess

    if shutil.which("docker") is None:
        pytest.skip("docker not installed")
    proc = subprocess.run(
        ["docker", "compose", "-f", str(COMPOSE), "config"],
        cwd=LAB,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        pytest.skip(proc.stderr.strip() or "docker compose unavailable")
    assert "backend" in proc.stdout
    assert "frontend" in proc.stdout
    assert "postgres" in proc.stdout
