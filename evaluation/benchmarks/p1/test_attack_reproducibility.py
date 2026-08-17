def test_attack_reproducibility(controller) -> None:
    a = controller.generate(controller.build_contract("ATO-001", difficulty="MEDIUM", transaction_count=120, seed=424242))
    b = controller.generate(controller.build_contract("ATO-001", difficulty="MEDIUM", transaction_count=120, seed=424242))
    assert a["amount"].tolist() == b["amount"].tolist()
    assert a["device_id"].tolist() == b["device_id"].tolist()
    assert a["fraud_label"].tolist() == b["fraud_label"].tolist()
    assert (a["fraud_label"] == 1).all()
