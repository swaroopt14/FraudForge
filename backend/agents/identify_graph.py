"""Identify-only LangGraph: retrieve → score → hypothesize.

Falls back to the same three functions if LangGraph is missing, and to the
catalog ranker if no NVIDIA/OpenAI key or the LLM call fails.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, TypedDict

from attack_catalog import ATTACK_CATALOG, CORE_FAMILY_IDS, IDENTITY_AUTH_FAMILY_IDS, catalog_status, diversity_metrics, hypothesis_from_catalog
from features import TRAIN_FAMILY_WEIGHTS

from .threat_intel import fetch_allowlisted, load_corpus, retrieve, tokenize

SYSTEM_PROMPT = """You are a payment-fraud researcher on a closed-loop blue-team exercise.
Given retrieved threat-intelligence notes and a family catalog, propose DISTINCT
GenAI-powered *payment fraud* attack hypotheses.

Rules:
- Defensive summaries only: names, surfaces, AI role, payment impact, detector signals.
- Do not write phishing copy, malware, exploits, or social-engineering scripts.
- Prefer catalog family ids when they fit. You may add a new snake_case family id
  only if the intel describes a payment attack that is not in the catalog.
- Cover as many DISTINCT families as the intel supports (target 6–10).
- Map OWASP LLM ids only when relevant (LLM01 prompt injection, LLM04 poisoning,
  LLM06 excessive agency, LLM08 retrieval poisoning, LLM09 misinformation, LLM10 unbounded use).

Return JSON: {"hypotheses": [ ... ]} with keys:
attack_name, attack_family, attack_surface, ai_component, payment_impact,
detectable_signals (subset of: device_new, velocity_1h, location_mismatch,
beneficiary_name_match, mule_account_risk, constraint_violation,
amount_vs_limit_ratio, Amount),
owasp_mapping (array of strings), confidence_score (0-1), source_ids (array).
"""

EVIDENCE_PRIOR = {
    "ESTABLISHED": 0.20,
    "EMERGING": 0.12,
    "PLAUSIBLE": 0.06,
    "SPECULATIVE": 0.0,
}
FEASIBILITY_PRIOR = {"HIGH": 0.12, "MEDIUM": 0.06, "LOW": 0.0}

DEFAULT_N = 12
CAP_N = 20
MIN_CATEGORIES = 8

try:
    from langgraph.graph import END, START, StateGraph

    HAS_LANGGRAPH = True
except Exception:  # noqa: BLE001
    HAS_LANGGRAPH = False
    END = START = StateGraph = None  # type: ignore[misc, assignment]


class IdentifyState(TypedDict, total=False):
    query: str
    fetch_live: bool
    docs: list[dict[str, Any]]
    ranked: list[tuple[str, float, list[str]]]
    hypotheses: list[dict[str, Any]]
    provider: str
    configured_provider: str | None
    llm_used: bool
    live_fetch: dict[str, Any]
    graph_runtime: str
    corpus_size: int


def _parse_hypotheses_blob(text: str) -> list[dict[str, Any]]:
    text = (text or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text).rstrip("`").strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.S) or re.search(r"\[.*\]", text, flags=re.S)
        if not match:
            return []
        parsed = json.loads(match.group(0))
    if isinstance(parsed, dict):
        data = parsed.get("hypotheses", parsed)
        if isinstance(data, dict):
            data = [data]
    elif isinstance(parsed, list):
        data = parsed
    else:
        return []
    return [row for row in data if isinstance(row, dict) and row.get("attack_name")]


def weighted_rank(query: str, docs: list[dict[str, Any]]) -> list[tuple[str, float, list[str]]]:
    """Keyword overlap + tagged intel + evidence/feasibility priors + novelty."""
    blob = " ".join([query] + [f"{d.get('title', '')} {d.get('summary', '')}" for d in docs])
    tokens = tokenize(blob)
    qtok = tokenize(query)
    trained = set(TRAIN_FAMILY_WEIGHTS)
    ranked: list[tuple[str, float, list[str]]] = []
    for fid, meta in ATTACK_CATALOG.items():
        keys = tokenize(" ".join(meta["keywords"] + [meta["name"], fid.replace("_", " ")]))
        overlap = len(tokens & keys)
        score = overlap / max(len(keys), 1)
        if qtok:
            score += 0.35 * len(qtok & keys)
        source_ids = [d["id"] for d in docs if fid in (d.get("families") or [])]
        if source_ids:
            score += 0.40
        score += EVIDENCE_PRIOR.get(str(meta.get("evidence") or ""), 0.0)
        score += FEASIBILITY_PRIOR.get(str(meta.get("feasibility") or ""), 0.0)
        if fid not in trained:
            score += 0.10
        ranked.append((fid, score, source_ids))
    ranked.sort(key=lambda row: row[1], reverse=True)
    return ranked


def _normalize_llm_row(row: dict[str, Any], index: int, docs: list[dict[str, Any]]) -> dict[str, Any]:
    family = str(row.get("attack_family") or "unspecified").strip().lower().replace(" ", "_")
    source_ids = row.get("source_ids") or []
    if not isinstance(source_ids, list):
        source_ids = [str(source_ids)]
    known_ids = {d["id"] for d in docs}
    source_ids = [str(s) for s in source_ids if s in known_ids]
    if not source_ids:
        source_ids = [d["id"] for d in docs[:2]]
    signals = row.get("detectable_signals") or []
    if isinstance(signals, str):
        signals = [s.strip() for s in signals.split(",") if s.strip()]
    owasp = row.get("owasp_mapping") or row.get("owasp") or []
    if isinstance(owasp, str):
        owasp = [owasp]
    confidence = row.get("confidence_score", 0.6)
    try:
        confidence = float(confidence)
    except (TypeError, ValueError):
        confidence = 0.6
    if family in ATTACK_CATALOG:
        base = hypothesis_from_catalog(
            family,
            confidence=max(confidence, 0.45),
            source_ids=source_ids,
            index=index,
        )
        if row.get("attack_name"):
            base["attack_name"] = row["attack_name"]
        if signals:
            base["detectable_signals"] = signals
        if owasp:
            base["owasp_mapping"] = owasp
        return base
    return {
        "hypothesis_id": f"HYP-{index:03d}",
        "attack_name": row.get("attack_name", "Unnamed"),
        "attack_family": family,
        "category": row.get("category"),
        "evidence": row.get("evidence", "PLAUSIBLE"),
        "feasibility": row.get("feasibility", "MEDIUM"),
        "tier": row.get("tier", 3),
        "attack_surface": row.get("attack_surface", "—"),
        "ai_component": row.get("ai_component", "—"),
        "payment_impact": row.get("payment_impact", "—"),
        "detectable_signals": list(signals),
        "signal_layers": dict(row.get("signal_layers") or {}),
        "owasp_mapping": list(owasp),
        "confidence_score": round(min(max(confidence, 0.0), 1.0), 3),
        "catalog_status": catalog_status(family),
        "source_ids": source_ids,
    }


def _ordered_rank(ranked: list[tuple[str, float, list[str]]]) -> list[tuple[str, float, list[str]]]:
    tagged = [row for row in ranked if row[2]]
    rest = [row for row in ranked if not row[2]]
    return tagged + rest


def hypotheses_from_ranked(
    docs: list[dict[str, Any]],
    ranked: list[tuple[str, float, list[str]]],
    n: int = DEFAULT_N,
    cap: int = CAP_N,
) -> list[dict[str, Any]]:
    ordered = _ordered_rank(ranked)
    take = min(max(n, 5), cap, len(ordered))
    selected: list[tuple[str, float, list[str]]] = []
    seen: set[str] = set()
    cats: set[str] = set()
    for fid, score, source_ids in ordered:
        if fid in seen:
            continue
        selected.append((fid, score, source_ids))
        seen.add(fid)
        cat = (ATTACK_CATALOG.get(fid) or {}).get("category")
        if cat:
            cats.add(str(cat))
        if len(selected) >= take:
            break
    if len(cats) < MIN_CATEGORIES:
        for fid, score, source_ids in ordered:
            if fid in seen:
                continue
            cat = (ATTACK_CATALOG.get(fid) or {}).get("category")
            if not cat or cat in cats:
                continue
            selected.append((fid, score, source_ids))
            seen.add(fid)
            cats.add(str(cat))
            if len(selected) >= cap or len(cats) >= MIN_CATEGORIES:
                break
    out = []
    for i, (fid, score, source_ids) in enumerate(selected, start=1):
        if not source_ids:
            source_ids = [d["id"] for d in docs[:2] if d.get("id")]
        confidence = min(0.95, 0.42 + score)
        out.append(hypothesis_from_catalog(fid, confidence=confidence, source_ids=source_ids, index=i))
    return _ensure_core_hypotheses(out, docs)


def _pad_hypotheses(
    rows: list[dict[str, Any]],
    docs: list[dict[str, Any]],
    ranked: list[tuple[str, float, list[str]]],
) -> list[dict[str, Any]]:
    unique: list[dict[str, Any]] = []
    have: set[str] = set()
    for row in rows:
        fid = row.get("attack_family")
        if not fid or fid in have:
            continue
        have.add(fid)
        unique.append({**row, "hypothesis_id": f"HYP-{len(unique) + 1:03d}"})
    extras = hypotheses_from_ranked(docs, ranked, n=DEFAULT_N, cap=CAP_N)
    cats = {
        str((ATTACK_CATALOG.get(r["attack_family"]) or {}).get("category") or r.get("category"))
        for r in unique
        if r.get("attack_family")
    }
    for extra in extras:
        if extra["attack_family"] in have:
            continue
        cat = extra.get("category")
        need_cat = cat and cat not in cats and len(cats) < MIN_CATEGORIES
        need_n = len(unique) < DEFAULT_N
        if not (need_n or need_cat):
            continue
        unique.append({**extra, "hypothesis_id": f"HYP-{len(unique) + 1:03d}"})
        have.add(extra["attack_family"])
        if cat:
            cats.add(str(cat))
        if len(unique) >= CAP_N:
            break
    return _ensure_core_hypotheses(unique, docs)[:CAP_N]


def _ensure_core_hypotheses(
    rows: list[dict[str, Any]],
    docs: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Keep BUILD REQUEST vectors and the identity/auth pack in every discovery run."""
    have = {r.get("attack_family") for r in rows}
    source_ids = [d["id"] for d in docs[:2] if d.get("id")]
    extras = []
    for fid in list(CORE_FAMILY_IDS) + list(IDENTITY_AUTH_FAMILY_IDS):
        if fid in have or fid not in ATTACK_CATALOG:
            continue
        extras.append(
            hypothesis_from_catalog(fid, confidence=0.74, source_ids=source_ids, index=0)
        )
        have.add(fid)
    merged = extras + rows
    out = []
    seen: set[str] = set()
    for row in merged:
        fid = row.get("attack_family")
        if not fid or fid in seen:
            continue
        seen.add(fid)
        out.append({**row, "hypothesis_id": f"HYP-{len(out) + 1:03d}"})
    return out


def _message_text(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                parts.append(str(item.get("text") or ""))
            else:
                parts.append(str(getattr(item, "text", "") or ""))
        return "".join(parts)
    return str(content)


def configured_llm_provider() -> str | None:
    if os.getenv("NVIDIA_API_KEY"):
        return "nvidia"
    if os.getenv("OPENAI_API_KEY"):
        return "openai"
    return None


def _complete_json(user_payload: dict[str, Any]) -> tuple[str | None, str | None]:
    """Return (raw_json, provider) using ChatOpenAI, then the OpenAI SDK."""
    provider = configured_llm_provider()
    if provider is None:
        return None, None
    system = SYSTEM_PROMPT
    user = json.dumps(user_payload)
    model = (
        os.getenv("NVIDIA_MODEL", "nvidia/llama-3.1-nemotron-ultra-253b-v1")
        if provider == "nvidia"
        else os.getenv("OPENAI_MODEL", "gpt-4o")
    )
    base_url = os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1") if provider == "nvidia" else None
    api_key = os.getenv("NVIDIA_API_KEY") if provider == "nvidia" else os.getenv("OPENAI_API_KEY")

    try:
        from langchain_openai import ChatOpenAI
        from langchain_core.messages import HumanMessage, SystemMessage

        kwargs: dict[str, Any] = {
            "model": model,
            "api_key": api_key,
            "temperature": 0.4,
        }
        if base_url:
            kwargs["base_url"] = base_url
        llm = ChatOpenAI(**kwargs)
        bound = llm.bind(response_format={"type": "json_object"})
        msg = bound.invoke([SystemMessage(content=system), HumanMessage(content=user)])
        raw = _message_text(getattr(msg, "content", None))
        if raw.strip():
            return raw, provider
    except Exception:  # noqa: BLE001
        pass

    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key, base_url=base_url) if base_url else OpenAI(api_key=api_key)
        resp = client.chat.completions.create(
            model=model,
            temperature=0.4,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        raw = resp.choices[0].message.content or "{}"
        return raw, provider
    except Exception:  # noqa: BLE001
        return None, None


def llm_hypotheses(query: str, docs: list[dict[str, Any]]) -> tuple[list[dict[str, Any]] | None, str | None]:
    catalog_brief = [
        {
            "id": fid,
            "name": meta["name"],
            "category": meta.get("category"),
            "evidence": meta.get("evidence"),
            "feasibility": meta.get("feasibility"),
            "tier": meta.get("tier"),
            "owasp": meta["owasp"],
            "simulatable": meta["simulatable"],
        }
        for fid, meta in ATTACK_CATALOG.items()
    ]
    intel = [
        {
            "id": d.get("id"),
            "title": d.get("title"),
            "summary": d.get("summary"),
            "families": d.get("families"),
        }
        for d in docs
    ]
    raw, provider = _complete_json(
        {
            "analyst_query": query,
            "retrieved_intel": intel,
            "family_catalog": catalog_brief,
        }
    )
    if not raw:
        return None, None
    try:
        rows = _parse_hypotheses_blob(raw)
    except Exception:  # noqa: BLE001
        return None, None
    cleaned = [_normalize_llm_row(row, i, docs) for i, row in enumerate(rows, start=1)]
    if not cleaned:
        return None, None
    return cleaned, provider


def retrieve_node(state: IdentifyState) -> dict[str, Any]:
    query = (state.get("query") or "").strip()
    fetch_live = bool(state.get("fetch_live"))
    docs = retrieve(query, k=16)
    live_meta: dict[str, Any] = {"attempted": fetch_live, "ok": 0, "failed": 0, "error": None}
    if fetch_live:
        live = fetch_allowlisted()
        live_meta["ok"] = live.get("ok", 0)
        live_meta["failed"] = live.get("failed", 0)
        live_meta["error"] = live.get("error")
        docs = (live.get("docs") or []) + docs
        docs = docs[:10]
    return {"docs": docs, "live_fetch": live_meta, "corpus_size": len(load_corpus())}


def score_node(state: IdentifyState) -> dict[str, Any]:
    ranked = weighted_rank(state.get("query") or "", state.get("docs") or [])
    return {"ranked": ranked}


def hypothesize_node(state: IdentifyState) -> dict[str, Any]:
    docs = state.get("docs") or []
    ranked = state.get("ranked") or weighted_rank(state.get("query") or "", docs)
    llm_rows, llm_provider = llm_hypotheses(state.get("query") or "", docs)
    if llm_rows:
        hypotheses = _pad_hypotheses(llm_rows, docs, ranked)
        return {
            "hypotheses": hypotheses,
            "provider": llm_provider or "catalog",
            "llm_used": True,
        }
    hypotheses = hypotheses_from_ranked(docs, ranked, n=DEFAULT_N, cap=CAP_N)
    return {
        "hypotheses": hypotheses,
        "provider": "catalog",
        "llm_used": False,
    }


def _compile_graph():
    graph = StateGraph(IdentifyState)
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("score", score_node)
    graph.add_node("hypothesize", hypothesize_node)
    graph.add_edge(START, "retrieve")
    graph.add_edge("retrieve", "score")
    graph.add_edge("score", "hypothesize")
    graph.add_edge("hypothesize", END)
    return graph.compile()


_COMPILED = None
if HAS_LANGGRAPH:
    try:
        _COMPILED = _compile_graph()
    except Exception:  # noqa: BLE001
        _COMPILED = None

GRAPH_RUNTIME = "langgraph" if _COMPILED is not None else "sequential"


def run_identify(threat_intel: str = "", fetch_live: bool = False) -> dict[str, Any]:
    initial: IdentifyState = {
        "query": (threat_intel or "").strip(),
        "fetch_live": bool(fetch_live),
        "docs": [],
        "ranked": [],
        "hypotheses": [],
        "provider": "catalog",
        "configured_provider": configured_llm_provider(),
        "llm_used": False,
        "live_fetch": {"attempted": False, "ok": 0, "failed": 0, "error": None},
        "graph_runtime": "langgraph" if _COMPILED is not None else "sequential",
        "corpus_size": len(load_corpus()),
    }
    if _COMPILED is not None:
        state = _COMPILED.invoke(initial)
    else:
        state = dict(initial)
        state.update(retrieve_node(state))
        state.update(score_node(state))
        state.update(hypothesize_node(state))
        state["graph_runtime"] = "sequential"
    hypotheses = state.get("hypotheses") or []
    return {
        "query": state.get("query") or "",
        "retrieved": state.get("docs") or [],
        "hypotheses": hypotheses,
        "diversity": diversity_metrics(hypotheses),
        "llm_used": bool(state.get("llm_used")),
        "provider": state.get("provider") or "catalog",
        "configured_provider": state.get("configured_provider"),
        "graph_runtime": state.get("graph_runtime") or ("langgraph" if _COMPILED is not None else "sequential"),
        "live_fetch": state.get("live_fetch") or {},
        "corpus_size": int(state.get("corpus_size") or len(load_corpus())),
    }


__all__ = [
    "GRAPH_RUNTIME",
    "HAS_LANGGRAPH",
    "configured_llm_provider",
    "hypotheses_from_ranked",
    "run_identify",
    "weighted_rank",
]
