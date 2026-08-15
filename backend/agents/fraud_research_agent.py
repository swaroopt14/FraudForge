"""Attack discovery: retrieve threat intel, propose distinct families, score diversity."""

from __future__ import annotations

import json
import os
from typing import Any

from attack_catalog import ATTACK_CATALOG, FAMILY_LABELS

from .identify_graph import GRAPH_RUNTIME, configured_llm_provider, run_identify


class FraudResearchAgent:
    def __init__(self) -> None:
        self._provider = configured_llm_provider()
        self._last_fallback = True
        self._last_graph = GRAPH_RUNTIME
        self._llm = None
        self._model = None
        self._init_briefing_llm()

    def _init_briefing_llm(self) -> None:
        nvidia_key = os.getenv("NVIDIA_API_KEY")
        openai_key = os.getenv("OPENAI_API_KEY")
        try:
            from openai import OpenAI
        except Exception:  # noqa: BLE001
            return
        if nvidia_key:
            self._llm = OpenAI(
                api_key=nvidia_key,
                base_url=os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1"),
            )
            self._provider = "nvidia"
            self._model = os.getenv("NVIDIA_MODEL", "nvidia/llama-3.1-nemotron-ultra-253b-v1")
            return
        if openai_key:
            self._llm = OpenAI()
            self._provider = "openai"
            self._model = os.getenv("OPENAI_MODEL", "gpt-4o")

    def discover(self, threat_intel: str = "", fetch_live: bool = False) -> dict[str, Any]:
        result = run_identify(threat_intel, fetch_live=fetch_live)
        self._last_fallback = not bool(result.get("llm_used"))
        self._last_graph = str(result.get("graph_runtime") or "sequential")
        if result.get("configured_provider"):
            self._provider = result.get("configured_provider")
        return result

    def generate_hypotheses(self, threat_intel: str) -> list[dict[str, Any]]:
        return self.discover(threat_intel)["hypotheses"]

    def scenario_card(self, family: str, n: int, method: str) -> str:
        """Blue-team briefing for a generated batch. No lure copy."""
        label = FAMILY_LABELS.get(family, family)
        meta = ATTACK_CATALOG.get(family) or {}
        fallback = (
            f"{n} synthetic rows via {method} + overlay for {label}. "
            f"Surface: {meta.get('attack_surface', 'payment session')}. "
            f"Detector should see {', '.join(meta.get('detectable_signals') or [])}."
        )
        if family in {"mixed", "", None}:
            fallback = (
                f"{n} mixed-family synthetic rows via {method} plus family overlay. "
                "Each row is stamped with overlay signals from its attack family."
            )
        if self._llm is None:
            return fallback
        try:
            resp = self._llm.chat.completions.create(
                model=self._model or os.getenv("OPENAI_MODEL", "gpt-4o"),
                temperature=0.3,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You write two-sentence blue-team briefings for synthetic payment-fraud rows. "
                            "Name the family, the tabular method, and which overlay signals a detector should see. "
                            "No phishing copy, no exploits, no step-by-step attacker instructions."
                        ),
                    },
                    {
                        "role": "user",
                        "content": json.dumps(
                            {
                                "family": family,
                                "label": label,
                                "n": n,
                                "method": method,
                                "surface": meta.get("attack_surface"),
                                "signals": meta.get("detectable_signals"),
                            }
                        ),
                    },
                ],
            )
            text = (resp.choices[0].message.content or "").strip()
            return text or fallback
        except Exception:  # noqa: BLE001
            return fallback

    @property
    def provider(self) -> str:
        if self._last_fallback:
            return "catalog"
        return self._provider or "catalog"

    @property
    def graph_runtime(self) -> str:
        return self._last_graph

    @property
    def using_fallback(self) -> bool:
        return self._last_fallback


__all__ = ["FraudResearchAgent"]
