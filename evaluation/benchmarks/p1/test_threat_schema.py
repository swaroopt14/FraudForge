from app.threats.loader import export_yaml, load_threats
from app.threats.schema import ThreatDefinition


def test_threat_schema() -> None:
    export_yaml()
    threats = load_threats()
    assert len(threats) >= 10
    for threat in threats:
        again = ThreatDefinition.model_validate(threat.model_dump())
        assert again.attack_id == threat.attack_id
        assert set(again.difficulty_levels) >= {"LOW", "MEDIUM", "HIGH"}
        assert len(again.variants) >= 5
        assert again.detection_signals
        assert again.simulation_template
        assert again.mutation_strategy
