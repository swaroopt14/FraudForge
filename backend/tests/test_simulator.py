from __future__ import annotations

from app.simulation.attacks import generate_attacks
from app.simulation.legit import fit_profiles, generate_legitimate


def test_legit_seed_deterministic(payments) -> None:
    profiles = fit_profiles(payments)
    a = generate_legitimate(profiles, 40, seed=11)
    b = generate_legitimate(profiles, 40, seed=11)
    assert a["amount"].tolist() == b["amount"].tolist()
    assert (a["fraud_label"] == 0).all()
    assert (a["attack_family"] == "").all()


def test_attack_count_and_seed(payments) -> None:
    a = generate_attacks(payments, "account_takeover", 50, seed=3)
    b = generate_attacks(payments, "account_takeover", 50, seed=3)
    assert len(a) == 50
    assert a["device_id"].tolist() == b["device_id"].tolist()
    assert (a["fraud_label"] == 1).all()
    assert (a["failed_auth_count"] >= 1).all()


def test_low_and_slow_keeps_amount_band(payments) -> None:
    legit = generate_legitimate(fit_profiles(payments), 60, seed=5)
    atk = generate_attacks(payments, "low_and_slow", 60, seed=5)
    # same seed base amounts before timing overlay — amounts stay near legit scale
    assert atk["amount"].median() < legit["amount"].median() * 3
    assert (atk["device_id"] == generate_legitimate(fit_profiles(payments), 60, seed=5)["device_id"]).all()


def test_amount_anomaly_changes_amount(payments) -> None:
    base = generate_legitimate(fit_profiles(payments), 40, seed=9)
    atk = generate_attacks(payments, "amount_anomaly", 40, seed=9)
    assert atk["amount"].mean() > base["amount"].mean() * 2


def test_each_family_mutates_its_columns(payments) -> None:
    base = generate_legitimate(fit_profiles(payments), 30, seed=12)
    ato = generate_attacks(payments, "account_takeover", 30, seed=12)
    vel = generate_attacks(payments, "velocity_attack", 30, seed=12)
    ben = generate_attacks(payments, "beneficiary_anomaly", 30, seed=12)
    assert (ato["device_id"] != base["device_id"]).all()
    assert (ato["failed_auth_count"] > 0).all()
    assert vel["transaction_count_1h"].mean() > base["transaction_count_1h"].mean()
    assert (ben["beneficiary_is_new"] == 1).all()
    assert (ben["beneficiary_id"] != base["beneficiary_id"]).all()
