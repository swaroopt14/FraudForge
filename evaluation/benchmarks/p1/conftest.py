from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "backend"))

from app.data.ingest import ingest, locate_ieee, normalize
from app.core.config import IEEE_DIR
from app.fraud.pipeline import BlueTeam, prepare_split
from app.redteam.controller import RedTeamController
from app.simulation.attacks import generate_mixed_attacks
from app.threats.loader import export_yaml, load_threats
from app.threats.registry import ThreatRegistry


def _tiny(n: int = 500) -> pd.DataFrame:
    rng = np.random.default_rng(0)
    n_fraud = 50
    return pd.DataFrame(
        {
            "TransactionID": np.arange(4_000_000, 4_000_000 + n),
            "isFraud": np.array([1] * n_fraud + [0] * (n - n_fraud)),
            "TransactionDT": rng.uniform(86_400, 2_000_000, n),
            "TransactionAmt": rng.lognormal(3.2, 0.8, n),
            "ProductCD": rng.choice(["W", "C", "H"], n),
            "card1": rng.integers(1000, 5000, n),
            "card4": rng.choice(["visa", "discover"], n),
            "card6": rng.choice(["debit", "credit"], n),
            "addr1": rng.integers(100, 400, n),
            "addr2": np.full(n, 87.0),
            "dist1": rng.uniform(0, 80, n),
            "D1": rng.uniform(0, 200, n),
            "C1": rng.integers(1, 6, n),
            "C2": rng.integers(1, 6, n),
            "DeviceType": rng.choice(["mobile", "desktop"], n),
            "DeviceInfo": rng.choice(["Pixel", "iOS Device", ""], n),
            "id_31": rng.choice(["chrome", "safari", ""], n),
        }
    )


@pytest.fixture(scope="session")
def payments() -> pd.DataFrame:
    try:
        locate_ieee(IEEE_DIR)
        return ingest(sample_n=2500, persist=False)
    except FileNotFoundError:
        return normalize(_tiny())


@pytest.fixture(scope="session")
def registry() -> ThreatRegistry:
    export_yaml()
    return ThreatRegistry(load_threats())


@pytest.fixture(scope="session")
def controller(payments, registry) -> RedTeamController:
    attacks = generate_mixed_attacks(payments, n_each=60)
    train, test = prepare_split(payments, attacks, seed=3)
    blue = BlueTeam()
    blue.train(train, test)
    return RedTeamController(payments, blue, registry)
