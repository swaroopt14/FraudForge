"""Identify catalog and offline discovery (no live LLM)."""

from __future__ import annotations

from attack_catalog import ATTACK_CATALOG, CORE_FAMILY_IDS, IDENTITY_AUTH_FAMILY_IDS, SIMULATABLE_FAMILIES
from agents.identify_graph import run_identify
from agents.threat_intel import load_corpus


def test_catalog_size_and_simulatable() -> None:
    assert len(ATTACK_CATALOG) >= 28
    assert len(SIMULATABLE_FAMILIES) >= 16
    for fid in SIMULATABLE_FAMILIES:
        assert ATTACK_CATALOG[fid]["simulatable"] is True
    for fid in CORE_FAMILY_IDS:
        assert fid in ATTACK_CATALOG
    for fid in IDENTITY_AUTH_FAMILY_IDS:
        assert fid in ATTACK_CATALOG
        assert ATTACK_CATALOG[fid]["simulatable"] is True


def test_hypothesis_fields(monkeypatch) -> None:
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    result = run_identify("", fetch_live=False)
    assert result["provider"] == "catalog"
    hyps = result["hypotheses"]
    assert len(hyps) >= 5
    row = hyps[0]
    for key in ("hypothesis_id", "attack_family", "evidence", "feasibility", "tier", "signal_layers"):
        assert key in row
    have = {h["attack_family"] for h in hyps}
    assert set(CORE_FAMILY_IDS) <= have
    assert set(IDENTITY_AUTH_FAMILY_IDS) <= have
    div = result["diversity"]
    assert div["n_distinct_families"] >= 12
    assert div["n_categories"] >= 8


def test_intel_corpus_tagged() -> None:
    notes = load_corpus()
    assert len(notes) >= 18
    assert all(n.get("families") for n in notes)
