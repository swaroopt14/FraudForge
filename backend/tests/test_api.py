from __future__ import annotations

from fastapi.testclient import TestClient

from app.fraud.pipeline import BlueTeam, prepare_split
from app.main import app
from app.simulation.attacks import generate_mixed_attacks
import app.service as service


def test_health_and_flow(payments, tmp_path, monkeypatch) -> None:
    from app.core import config, db as dbmod

    monkeypatch.setattr(config, "DATABASE_URL", f"sqlite:///{tmp_path / 't.db'}")
    dbmod._engine = None
    dbmod._Session = None
    attacks = generate_mixed_attacks(payments, n_each=50)
    train, test = prepare_split(payments, attacks, seed=3)
    blue = BlueTeam()
    blue.train(train, test)
    service._team = blue
    service._payments = payments

    client = TestClient(app)
    assert client.get("/health").json()["status"] == "ok"
    assert len(client.get("/attacks").json()["attacks"]) >= 5
    gen = client.post(
        "/simulation/generate",
        json={"attack_id": "amount_anomaly", "transaction_count": 40, "seed": 8, "intensity": "medium"},
    )
    assert gen.status_code == 200
    body = gen.json()
    assert body["generated"] == 40
    assert "report" in body
    assert body["narrative"]["finding"]
    sid = body["simulation_id"]
    got = client.get(f"/simulations/{sid}")
    assert got.status_code == 200
    assert "ADVERSARIAL PAYMENT DEFENSE" in got.json()["report"]
    metrics = client.get("/model/metrics").json()
    assert "lightgbm" in metrics
    importance = client.get("/model/feature-importance").json()["features"]
    assert len(importance) >= 1
    assert importance[0]["importance"] > 0
    score = client.post("/transactions/score", json={"transactions": body["preview"][:3]})
    assert score.status_code == 200
    assert 0 <= score.json()["results"][0]["fraud_probability"] <= 1
