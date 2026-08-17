def test_attack_variants(registry, controller) -> None:
    pairs = {(t.attack_id, v.id) for t, v in registry.all_variants()}
    assert len(pairs) >= 50
    v1 = controller.generate(controller.build_contract("ATO-001", variant_id="ATO-V01", difficulty="LOW", transaction_count=80, seed=7))
    v2 = controller.generate(controller.build_contract("ATO-001", variant_id="ATO-V05", difficulty="HIGH", transaction_count=80, seed=7))
    assert v1["device_id"].tolist() != v2["device_id"].tolist() or abs(v1["amount"].mean() - v2["amount"].mean()) > 1.0
