"""FastAPI handlers without spinning up lifespan / detector load."""

from __future__ import annotations

from app import catalog, health, sim_scenarios


def test_health_ok() -> None:
    assert health() == {"status": "ok"}


def test_catalog_endpoint() -> None:
    payload = catalog()
    assert payload["n"] >= 28
    assert len(payload["simulatable"]) >= 16
    assert len(payload["core_vectors"]) == 5


def test_simulation_scenarios_endpoint() -> None:
    payload = sim_scenarios()
    assert payload["n"] >= 4
    ids = {row["scenario_id"] for row in payload["scenarios"]}
    assert "agent_destination_substitution" in ids
