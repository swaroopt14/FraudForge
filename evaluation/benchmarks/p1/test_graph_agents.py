from fastapi.testclient import TestClient

from app.core.config import FEATURE_COLUMNS
from app.main import app
from app.redteam.graph import edge_fingerprint, graph_payload
import app.service as service
from app.core import config, db as dbmod


def test_edge_table_replay_and_agents(controller) -> None:
    first = controller.run(
        "MUL-001",
        difficulty="MEDIUM",
        transaction_count=60,
        seed=42,
        persist=True,
        explain=False,
    )
    assert first["graph"]["n_edges"] > 0
    assert first["graph"]["edge_fingerprint"]
    assert first["graph"]["focus"]["nodes"]
    assert first["graph"]["path"]
    replayed = controller.replay(first["simulation_id"], persist=False)
    assert replayed["graph"]["edge_fingerprint"] == first["graph"]["edge_fingerprint"]
    rows = controller.generate(
        controller.build_contract("MUL-001", difficulty="MEDIUM", transaction_count=60, seed=42)
    )
    assert edge_fingerprint(graph_payload(rows)["edge_table"]) == first["graph"]["edge_fingerprint"]


def test_agt_int_agent_events(controller) -> None:
    agt = controller.run("AGT-001", difficulty="LOW", transaction_count=40, seed=5, persist=False, explain=False)
    assert agt["agent_event_count"] == 40
    assert all(e["agent_id"] for e in agt["agent_events"])
    intent = controller.run("INT-001", difficulty="LOW", transaction_count=40, seed=5, persist=False, explain=False)
    assert intent["agent_event_count"] == 40
    assert all(e["reason"] in {"intent_match", "intent_mismatch"} for e in intent["agent_events"])
    assert "agent_id" not in FEATURE_COLUMNS
    assert "intent_id" not in FEATURE_COLUMNS


def test_adaptive_deterministic(controller) -> None:
    a = controller.run("ATO-001", difficulty="ADAPTIVE", transaction_count=50, seed=77, persist=False, explain=False)
    b = controller.run("ATO-001", difficulty="ADAPTIVE", transaction_count=50, seed=77, persist=False, explain=False)
    assert a["difficulty"] == "ADAPTIVE"
    assert a["contract"]["mutation"] == b["contract"]["mutation"]
    assert a["graph"]["edge_fingerprint"] == b["graph"]["edge_fingerprint"]


def test_graph_api(controller, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(config, "DATABASE_URL", f"sqlite:///{tmp_path / 'graph.db'}")
    dbmod._engine = None
    dbmod._Session = None
    service._controller = controller
    service._team = controller.team
    service._payments = controller.payments
    client = TestClient(app)
    run = client.post(
        "/red-team/run",
        json={"attack_id": "DEV-001", "difficulty": "MEDIUM", "transaction_count": 40, "seed": 3},
    )
    assert run.status_code == 200
    sid = run.json()["simulation_id"]
    graph = client.get(f"/red-team/runs/{sid}/graph")
    assert graph.status_code == 200
    body = graph.json()
    assert body["nodes"]
    assert body["edge_table"]
