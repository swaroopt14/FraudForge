def test_attack_scaling(controller) -> None:
    small = controller.generate(controller.build_contract("VEL-001", difficulty="MEDIUM", transaction_count=1000, seed=11))
    mid = controller.generate(controller.build_contract("VEL-001", difficulty="MEDIUM", transaction_count=10000, seed=11))
    assert len(small) == 1000
    assert len(mid) == 10000
    rel = abs(float(small["amount"].mean()) - float(mid["amount"].mean())) / max(float(small["amount"].mean()), 1e-6)
    assert rel < 0.35
    large = controller.generate(controller.build_contract("VEL-001", difficulty="MEDIUM", transaction_count=100_000, seed=11))
    assert len(large) == 100_000
    rel2 = abs(float(mid["amount"].mean()) - float(large["amount"].mean())) / max(float(mid["amount"].mean()), 1e-6)
    assert rel2 < 0.35
