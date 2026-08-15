"""Precomputed closed-loop demo artifact (no retrain)."""

from __future__ import annotations

import json

from config import CLOSED_LOOP_PATH


def test_closed_loop_demo_improves_attack_success() -> None:
    assert CLOSED_LOOP_PATH.exists()
    payload = json.loads(CLOSED_LOOP_PATH.read_text())
    before = payload["attack_success_before"]["attack_success_rate"]
    after = payload["attack_success_after"]["attack_success_rate"]
    assert before > 0.5
    assert after < before
    assert after < 0.1
    assert payload["mixed_test_after"]["f1"] > payload["mixed_test_before"]["f1"]
