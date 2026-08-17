from app.ops import parse_benchmark_text, run_metrics, threat_detail


def test_parse_benchmark_pass() -> None:
    text = """
P1 BENCHMARK
Threat Coverage            PASS
Fidelity                   PASS
P1 STATUS: PASS
"""
    parsed = parse_benchmark_text(text)
    assert parsed["status"] == "PASS"
    assert {c["label"]: c["result"] for c in parsed["checks"]}["Fidelity"] == "PASS"


def test_run_metrics_falls_back_to_nested() -> None:
    payload = run_metrics(
        {
            "simulation_id": "abc",
            "attack_id": "BEN-001",
            "n": 1000,
            "metrics": {"detection_rate": 0.001, "precision": 1.0, "pr_auc": 0.985, "fidelity": {"overall_fidelity": 0.78}},
        }
    )
    assert payload["generated"] == 1000
    assert payload["detected"] == 1
    assert payload["missed"] == 999
    assert payload["fidelity"] == 0.78


def test_threat_detail_ben() -> None:
    body = threat_detail("BEN-001")
    assert body["attack_id"] == "BEN-001"
    assert body["variants"] >= 5
    assert "beneficiary_is_new" in body["detection_signals"]
