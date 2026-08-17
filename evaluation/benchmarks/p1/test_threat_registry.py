def test_threat_registry(registry) -> None:
    assert len(registry.list()) >= 10
    assert registry.variant_count() >= 50
    threat = registry.get("ATO-001")
    assert threat.family == "account_takeover"
    variant = registry.resolve_variant("ATO-001", "ATO-V01")
    assert variant.id == "ATO-V01"
    mut = registry.mutation("ATO-001", "LOW", "ATO-V01")
    assert mut.device_change_probability >= 0
