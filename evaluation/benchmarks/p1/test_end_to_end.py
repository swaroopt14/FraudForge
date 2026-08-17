def test_end_to_end(controller) -> None:
    result = controller.run(
        "ATO-001",
        variant_id="ATO-V01",
        difficulty="LOW",
        transaction_count=80,
        seed=424242,
        persist=True,
        explain=False,
    )
    assert result["generated"] == 80
    assert "RED TEAM ATTACK REPORT" in result["report"]
    assert "metrics" in result
    replayed = controller.replay(result["simulation_id"], persist=False)
    first = controller.generate(controller.build_contract("ATO-001", variant_id="ATO-V01", difficulty="LOW", transaction_count=80, seed=424242))
    second = controller.generate(controller.build_contract("ATO-001", variant_id="ATO-V01", difficulty="LOW", transaction_count=80, seed=424242))
    assert first["amount"].tolist() == second["amount"].tolist()
    assert replayed["attack_id"] == "ATO-001"
