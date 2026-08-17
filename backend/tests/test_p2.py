from __future__ import annotations

import pandas as pd
from fastapi.testclient import TestClient

from app.blue_team.features import attach_p2_features, feature_matrix_v020
from app.blue_team.models import BlueTeamV2
from app.blue_team.service import train_p2
from app.core.config import FEATURE_COLUMNS, FEATURE_COLUMNS_V020, LEAKAGE_COLUMNS
from app.fraud.pipeline import BlueTeam, compute_metrics, feature_matrix, prepare_split
from app.main import app
from app.simulation.attacks import generate_mixed_attacks
from app.simulation.p2_attacks import generate_p2_attacks, generate_mixed_p2_attacks
import app.blue_team.service as blue_service
import app.service as service


def test_p0_feature_columns_frozen() -> None:
    assert "attack_family" not in FEATURE_COLUMNS
    assert "fraud_label" not in FEATURE_COLUMNS
    assert len(FEATURE_COLUMNS) == 15


def test_v020_no_label_leakage(payments) -> None:
    leaked = [c for c in FEATURE_COLUMNS_V020 if c in LEAKAGE_COLUMNS]
    assert leaked == []
    mule = generate_p2_attacks(payments, "mule_network", 40, seed=4)
    X = feature_matrix_v020(mule)
    assert list(X.columns) == FEATURE_COLUMNS_V020
    for col in LEAKAGE_COLUMNS:
        assert col not in X.columns
    feat = attach_p2_features(mule)
    assert feat["beneficiary_fan_in"].max() >= 8
    assert feat["device_is_shared"].max() >= 1.0


def test_p2_attacks_deterministic(payments) -> None:
    a = generate_p2_attacks(payments, "mule_network", 30, seed=11)
    b = generate_p2_attacks(payments, "mule_network", 30, seed=11)
    assert a["beneficiary_id"].tolist() == b["beneficiary_id"].tolist()
    assert (a["fraud_label"] == 1).all()
    geo = generate_p2_attacks(payments, "geo_anomaly", 12, seed=2)
    assert geo["customer_id"].nunique() == 1
    assert geo["country"].nunique() >= 2
    dev = generate_p2_attacks(payments, "shared_device", 20, seed=3)
    assert dev["device_id"].nunique() == 1
    assert dev["customer_id"].nunique() == 20


def test_p2_catches_coordinated_fraud_p0_misses(payments) -> None:
    p0_atk = generate_mixed_attacks(payments, n_each=40)
    train, test = prepare_split(payments, p0_atk, seed=1)
    p0 = BlueTeam()
    p0.train(train, test)

    p2_raw = generate_mixed_p2_attacks(payments, n_each=40)
    p2_atk = pd.concat(
        [attach_p2_features(part) for _, part in p2_raw.groupby("attack_family", sort=False)],
        ignore_index=True,
    )
    mix_train, mix_test = prepare_split(
        payments,
        pd.concat([p0_atk, p2_atk], ignore_index=True).sample(frac=1.0, random_state=2),
        seed=2,
    )
    p2 = BlueTeamV2()
    p2.train(mix_train, mix_test)

    mule = attach_p2_features(generate_p2_attacks(payments, "mule_network", 60, seed=9))
    legit = payments.loc[payments["fraud_label"] == 0].head(60)
    mix = pd.concat([mule, legit], ignore_index=True) if len(legit) else mule
    p0_m = compute_metrics(mix["fraud_label"].to_numpy(), p0.score(mix))
    p2_m = compute_metrics(mix["fraud_label"].to_numpy(), p2.score(mix))
    assert p2_m["recall"] > p0_m["recall"]
    assert p2_m["recall"] >= 0.5

    geo = generate_p2_attacks(payments, "geo_anomaly", 24, seed=5)
    feat = attach_p2_features(geo)
    assert feat["geo_impossible_travel"].max() >= 1.0
    geo_mix = pd.concat([geo, legit.head(24)], ignore_index=True) if len(legit) else geo
    assert compute_metrics(geo_mix["fraud_label"].to_numpy(), p2.score(geo_mix))["recall"] >= compute_metrics(
        geo_mix["fraud_label"].to_numpy(), p0.score(geo_mix)
    )["recall"]

    p0_x = feature_matrix(mule)
    assert list(p0_x.columns) == FEATURE_COLUMNS
    assert "beneficiary_fan_in" not in p0_x.columns
    assert "geo_impossible_travel" not in p0_x.columns


def test_blue_api_stream(payments, tmp_path, monkeypatch) -> None:
    from app.core import config, db as dbmod
    from app.blue_team import models as blue_models

    models_dir = tmp_path / "models"
    eval_dir = tmp_path / "eval"
    models_dir.mkdir()
    eval_dir.mkdir()
    monkeypatch.setattr(config, "DATABASE_URL", f"sqlite:///{tmp_path / 'p2.db'}")
    monkeypatch.setattr(config, "MODELS_DIR", models_dir)
    monkeypatch.setattr(config, "EVAL_DIR", eval_dir)
    monkeypatch.setattr(blue_models, "MODELS_DIR", models_dir)
    monkeypatch.setattr(blue_service, "MODELS_DIR", models_dir)
    monkeypatch.setattr(blue_service, "EVAL_DIR", eval_dir)
    dbmod._engine = None
    dbmod._Session = None
    from app.blue_team import store as blue_store

    blue_store.clear()
    p0_atk = generate_mixed_attacks(payments, n_each=30)
    p0 = BlueTeam()
    tr, te = prepare_split(payments, p0_atk, seed=3)
    p0.train(tr, te)
    service._team = p0
    service._payments = payments

    team = train_p2(payments, n_each=30)
    blue_service._p2 = team

    client = TestClient(app)
    empty = client.get("/blue/dashboard").json()
    assert empty["data_available"] is False or "transactions" in empty

    gen = client.post(
        "/simulation/generate",
        json={"attack_id": "mule_network", "transaction_count": 40, "seed": 8, "intensity": "medium"},
    )
    assert gen.status_code == 200
    body = gen.json()
    assert body["attack_family"] == "mule_network"
    assert "BLUE DEFENSE REPORT" in body["report"]
    assert body["narrative"]["finding"]

    dash = client.get("/blue/dashboard").json()
    assert dash["data_available"] is True
    assert dash["transactions"] == 40
    for key in ("precision", "recall", "f1", "pr_auc", "fpr", "detection_rate"):
        assert key in dash

    dets = client.get("/blue/detections").json()["detections"]
    assert len(dets) == 40
    detail = client.get(f"/blue/detections/{dets[0]['transaction_id']}").json()
    assert "signals" in detail
    assert "risk_score" in detail

    net = client.get("/blue/network").json()
    assert net["data_available"] is True
    assert net["suspicious_beneficiaries"] >= 1

    queue = client.get("/blue/mitigation").json()
    assert "counts" in queue
    tx = queue["items"][0]["transaction_id"]
    acted = client.post(f"/blue/mitigation/{tx}", json={"action": "BLOCK", "reason": "test"}).json()
    assert acted["action"] == "BLOCK"

    report = client.get(f"/blue/reports/{body['simulation_id']}").json()
    assert report["data_available"] is True
    aliases = client.get("/api/blue/dashboard").json()
    assert aliases["data_available"] is True


def test_catalog_includes_p2() -> None:
    client = TestClient(app)
    attacks = client.get("/attacks").json()["attacks"]
    ids = {row["id"] for row in attacks}
    assert len(attacks) >= 10
    assert "mule_network" in ids
    assert "geo_anomaly" in ids
