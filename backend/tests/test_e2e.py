from __future__ import annotations

from app.evaluation.report import render_report
from app.fraud.pipeline import BlueTeam, prepare_split
from app.service import run_simulation
from app.simulation.attacks import generate_mixed_attacks
import app.service as service


def test_red_team_workflow(payments, tmp_path, monkeypatch) -> None:
    from app.core import config, db as dbmod

    monkeypatch.setattr(config, "DATABASE_URL", f"sqlite:///{tmp_path / 'e2e.db'}")
    dbmod._engine = None
    dbmod._Session = None
    attacks = generate_mixed_attacks(payments, n_each=60)
    train, test = prepare_split(payments, attacks, seed=4)
    blue = BlueTeam()
    blue.train(train, test)
    service._team = blue
    service._payments = payments
    result = run_simulation("low_and_slow", 200, seed=424242, intensity="medium")
    assert result["generated"] == 200
    assert "metrics" in result
    for key in ("precision", "recall", "f1", "pr_auc", "fpr"):
        assert key in result["metrics"]
    assert "missed_transactions" in result
    text = result["report"]
    assert "RUN #" in text
    assert str(200) in text
    from app.core.config import REPORTS_DIR

    written = list(REPORTS_DIR.glob("run_*.txt"))
    assert written
    sample = render_report("x", "low_and_slow", 200, result["metrics"])
    assert "False-positive rate" in sample
    assert (REPORTS_DIR / "run_x.json").exists()
