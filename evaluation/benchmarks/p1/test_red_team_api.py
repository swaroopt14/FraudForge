from fastapi.testclient import TestClient

from app.main import app
import app.service as service
from app.core import config, db as dbmod


def test_red_team_api(controller, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(config, "DATABASE_URL", f"sqlite:///{tmp_path / 'p1.db'}")
    dbmod._engine = None
    dbmod._Session = None
    service._controller = controller
    service._team = controller.team
    service._payments = controller.payments

    client = TestClient(app)
    threats = client.get("/threats")
    assert threats.status_code == 200
    assert threats.json()["n"] >= 10
    assert threats.json()["variants"] >= 50
    detail = client.get("/threats/ATO-001")
    assert detail.status_code == 200
    run = client.post(
        "/red-team/run",
        json={"attack_id": "AMT-001", "difficulty": "LOW", "transaction_count": 40, "seed": 9},
    )
    assert run.status_code == 200
    body = run.json()
    assert "RED TEAM ATTACK REPORT" in body["report"]
    sid = body["simulation_id"]
    got = client.get(f"/red-team/runs/{sid}")
    assert got.status_code == 200
    report = client.get(f"/red-team/runs/{sid}/report")
    assert "RED TEAM ATTACK REPORT" in report.json()["report"]
    graph = client.get(f"/red-team/runs/{sid}/graph")
    assert graph.status_code == 200
    assert "nodes" in graph.json()
    replay = client.post("/red-team/replay", json={"simulation_id": sid})
    assert replay.status_code == 200
    board = client.get("/red-team/leaderboard")
    assert board.status_code == 200
    history = client.get("/red-team/history")
    assert history.status_code == 200
    assert history.json()["history"]
    lab = client.get("/blue-team")
    assert lab.status_code == 200
    assert lab.json()["model_version"]
    assert lab.json()["history"]
    assert "detection_rate" in lab.json()["history"][0]
    assert client.get("/red-team/benchmarks").status_code == 200
    assert client.get("/models/registry").status_code == 200
    rec = client.post("/red-team/recommend")
    assert rec.status_code == 200
    assert rec.json()["not"] == "fraud_probability"
    assert client.get(f"/red-team/runs/{sid}/blue-report").status_code == 200
    fb = client.get(f"/red-team/runs/{sid}/feedback")
    assert fb.status_code == 200
    assert fb.json()["linked"] is True


def test_ops_surface_aliases(controller, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(config, "DATABASE_URL", f"sqlite:///{tmp_path / 'ops.db'}")
    dbmod._engine = None
    dbmod._Session = None
    service._controller = controller
    service._team = controller.team
    service._payments = controller.payments

    client = TestClient(app)
    dest = client.get("/threats", params={"category": "destination"})
    assert dest.status_code == 200
    assert dest.json()["n"] >= 1
    dash = client.get("/dashboard/summary")
    assert dash.status_code == 200
    assert "precision" in dash.json()
    assert client.get("/dashboard/recent-runs").status_code == 200
    created = client.post(
        "/red-team/runs",
        json={"attack_id": "BEN-001", "difficulty": "MEDIUM", "scale": 40, "seed": 11},
    )
    assert created.status_code == 200
    sid = created.json()["simulation_id"]
    assert "generated" in created.json()
    assert client.get(f"/red-team/runs/{sid}/metrics").status_code == 200
    assert client.get(f"/red-team/runs/{sid}/signals").status_code == 200
    assert client.get(f"/red-team/runs/{sid}/timeline").json()["stages"]
    assert client.get(f"/red-team/runs/{sid}/misses").status_code == 200
    replay = client.post(f"/red-team/runs/{sid}/replay")
    assert replay.status_code == 200
    model = client.get("/blue-team/model")
    assert model.status_code == 200
    assert model.json()["features"] == 15
    risk = client.get("/blue-team/risk-summary").json()
    assert risk["network"]["enabled"] is False
    assert risk["network"]["phase"] == "P2"
    assert client.get("/blue-team/features").status_code == 200
    assert client.get("/blue-team/decision-distribution").status_code == 200
    txs = client.get("/transactions", params={"simulation_id": sid, "limit": 10})
    assert txs.status_code == 200
    assert client.get("/evaluation/summary").status_code == 200
    assert client.get("/evaluation/attack-matrix").status_code == 200
    bench = client.get("/benchmarks/current")
    assert bench.status_code == 200
    assert bench.json()["phase"] == "p1"
    assert client.get("/benchmarks/p2").json()["phase"] == "p2"
    assert client.get("/model/confusion-matrix").status_code == 200
    assert client.get("/model/pr-curve").status_code == 200
    assert client.get("/model/threshold-sweep").status_code == 200
