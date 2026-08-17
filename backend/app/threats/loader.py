"""Load and persist validated threat YAML."""

from __future__ import annotations

from pathlib import Path

import yaml

from app.core.config import THREATS_DIR, ensure_dirs
from app.threats.catalog import THREATS
from app.threats.schema import ThreatDefinition


def export_yaml(directory: Path | None = None) -> list[Path]:
    ensure_dirs()
    root = directory or THREATS_DIR
    root.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for raw in THREATS:
        threat = ThreatDefinition.model_validate(raw)
        path = root / f"{threat.attack_id}.yaml"
        path.write_text(yaml.safe_dump(threat.model_dump(), sort_keys=False))
        written.append(path)
    return written


def load_threats(directory: Path | None = None) -> list[ThreatDefinition]:
    ensure_dirs()
    root = directory or THREATS_DIR
    files = sorted(root.glob("*.yaml"))
    catalog_variants = sum(len(t.get("variants") or []) for t in THREATS)
    if len(files) < 10:
        export_yaml(root)
        files = sorted(root.glob("*.yaml"))
    threats = []
    for path in files:
        data = yaml.safe_load(path.read_text())
        threats.append(ThreatDefinition.model_validate(data))
    loaded_variants = sum(len(t.variants) for t in threats)
    if loaded_variants < catalog_variants:
        export_yaml(root)
        threats = []
        for path in sorted(root.glob("*.yaml")):
            data = yaml.safe_load(path.read_text())
            threats.append(ThreatDefinition.model_validate(data))
    return threats
