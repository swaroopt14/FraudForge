"""Novelty vs threat library and prior generated attacks. Not an LLM claim."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import joblib
import numpy as np
from sklearn.feature_extraction.text import HashingVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from app.core.config import MODELS_DIR, SIM_DIR, ensure_dirs
from app.threats.registry import get_registry

VERSION = "RED-NOVELTY-0.1.0"
ARTIFACT = MODELS_DIR / VERSION / "vectorizer.joblib"


def _embedder():
    try:
        from sentence_transformers import SentenceTransformer

        return ("sentence-transformers", SentenceTransformer("all-MiniLM-L6-v2"))
    except Exception:
        return ("hashing", HashingVectorizer(n_features=256, alternate_sign=False, norm="l2"))


def attack_text(threat, mutation=None) -> str:
    m = mutation.model_dump() if mutation is not None and hasattr(mutation, "model_dump") else (mutation or {})
    parts = [
        getattr(threat, "attack_id", ""),
        getattr(threat, "name", ""),
        getattr(threat, "objective", ""),
        getattr(threat, "category", ""),
        getattr(threat, "family", ""),
        getattr(threat, "mutation_strategy", ""),
        getattr(threat, "network_strategy", ""),
        " ".join(getattr(threat, "evasion_strategies", []) or []),
        json.dumps(m, sort_keys=True, default=str),
    ]
    return " ".join(str(p) for p in parts if p)


class RedTeamNoveltyModel:
    def __init__(self) -> None:
        self.backend, self.model = _embedder()
        self.version = VERSION
        self._library_texts: list[str] = []
        self._library_ids: list[str] = []
        self._library_mat = None
        self._fit_library()

    def _encode(self, texts: list[str]):
        if self.backend == "sentence-transformers":
            return np.asarray(self.model.encode(texts, normalize_embeddings=True))
        return self.model.transform(texts)

    def _fit_library(self) -> None:
        registry = get_registry()
        self._library_ids = []
        self._library_texts = []
        for threat in registry.list():
            self._library_ids.append(threat.attack_id)
            self._library_texts.append(attack_text(threat))
        if SIM_DIR.exists():
            for path in SIM_DIR.glob("*.json"):
                try:
                    data = json.loads(path.read_text())
                    tid = str(data.get("attack_id") or path.stem)
                    text = f"{tid} {data.get('attack_name') or ''} {data.get('finding') or ''} {json.dumps(data.get('contract') or {}, default=str)}"
                    self._library_ids.append(f"sim:{tid}")
                    self._library_texts.append(text)
                except Exception:
                    continue
        if self._library_texts:
            self._library_mat = self._encode(self._library_texts)

    def score_text(self, text: str, exclude_id: str | None = None) -> dict[str, Any]:
        if self._library_mat is None or not self._library_texts:
            return {
                "novelty_score": 100.0,
                "nearest_known_attack": None,
                "similarity": 0.0,
                "status": "novel_candidate",
                "backend": self.backend,
                "model_version": self.version,
            }
        query = self._encode([text])
        sims = cosine_similarity(query, self._library_mat)[0]
        best_i = None
        best = -1.0
        for i, sim in enumerate(sims):
            ident = self._library_ids[i]
            if exclude_id and (ident == exclude_id or ident.endswith(exclude_id)):
                continue
            if float(sim) > best:
                best = float(sim)
                best_i = i
        similarity = max(0.0, best)
        novelty = float(max(0.0, min(100.0, (1.0 - similarity) * 100.0)))
        if novelty >= 70:
            status = "novel_candidate"
        elif novelty >= 40:
            status = "related_variant"
        else:
            status = "known_near_duplicate"
        nearest = self._library_ids[best_i] if best_i is not None else None
        if nearest and nearest.startswith("sim:"):
            nearest = nearest.split(":", 1)[1]
        return {
            "novelty_score": round(novelty, 2),
            "nearest_known_attack": nearest,
            "similarity": round(similarity, 4),
            "status": status,
            "backend": self.backend,
            "model_version": self.version,
        }

    def score_threat(self, threat, mutation=None) -> dict[str, Any]:
        return self.score_text(attack_text(threat, mutation), exclude_id=threat.attack_id)

    def save(self, path: Path | None = None) -> Path:
        ensure_dirs()
        dest = path or ARTIFACT
        dest.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump({"backend": self.backend, "version": self.version}, dest)
        (dest.parent / "VERSION.json").write_text(json.dumps({"model_version": self.version, "backend": self.backend}, indent=2))
        return dest
