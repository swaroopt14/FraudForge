"""Load, retrieve, and optionally fetch allowlisted public threat-intel notes."""

from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urlparse

from config import THREAT_INTEL_PATH

STOP = {
    "the", "and", "for", "that", "with", "from", "this", "are", "was", "were",
    "have", "has", "not", "but", "into", "their", "they", "than", "then",
    "also", "can", "will", "its", "via", "per", "over", "after", "before",
}


def tokenize(text: str) -> set[str]:
    words = re.findall(r"[a-z][a-z0-9_-]{2,}", (text or "").lower())
    return {w for w in words if w not in STOP}


def load_corpus() -> list[dict[str, Any]]:
    if not THREAT_INTEL_PATH.exists():
        return []
    payload = json.loads(THREAT_INTEL_PATH.read_text())
    return list(payload.get("sources") or [])


def _score_doc(query_tokens: set[str], doc: dict[str, Any]) -> float:
    blob = " ".join(
        [
            doc.get("title") or "",
            doc.get("summary") or "",
            " ".join(doc.get("families") or []),
        ]
    )
    doc_tokens = tokenize(blob)
    if not query_tokens:
        return 0.15 + 0.05 * len(doc.get("families") or [])
    overlap = query_tokens & doc_tokens
    return len(overlap) / (len(query_tokens) ** 0.5)


def retrieve(query: str, k: int = 6) -> list[dict[str, Any]]:
    corpus = load_corpus()
    tokens = tokenize(query)
    ranked = []
    for doc in corpus:
        score = _score_doc(tokens, doc)
        item = dict(doc)
        item["score"] = round(float(score), 3)
        item["origin"] = "corpus"
        ranked.append(item)
    ranked.sort(key=lambda d: d["score"], reverse=True)
    if not tokens:
        return ranked[:k]
    hits = [d for d in ranked if d["score"] > 0]
    return (hits or ranked)[:k]


def allowlisted_urls() -> list[str]:
    urls = []
    for doc in load_corpus():
        url = doc.get("url") or ""
        host = urlparse(url).hostname or ""
        if host.endswith("mastercard.com") or host.endswith("owasp.org"):
            urls.append(url)
    # Stable unique order
    seen: set[str] = set()
    out = []
    for url in urls:
        if url not in seen:
            seen.add(url)
            out.append(url)
    return out[:4]


def _extract_preview(html: str, limit: int = 700) -> str:
    html = re.sub(r"(?is)<script.*?>.*?</script>", " ", html)
    html = re.sub(r"(?is)<style.*?>.*?</style>", " ", html)
    title_m = re.search(r"(?is)<title[^>]*>(.*?)</title>", html)
    meta_m = re.search(
        r'(?is)<meta[^>]+(?:name|property)=["\'](?:description|og:description)["\'][^>]+content=["\']([^"\']+)',
        html,
    )
    if not meta_m:
        meta_m = re.search(
            r'(?is)<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:name|property)=["\'](?:description|og:description)["\']',
            html,
        )
    text = re.sub(r"(?is)<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text).strip()
    parts: list[str] = []
    if title_m:
        parts.append(re.sub(r"\s+", " ", title_m.group(1)).strip())
    if meta_m:
        parts.append(meta_m.group(1).strip())
    if text:
        parts.append(text[:limit])
    return " — ".join(parts)[:1200]


def fetch_allowlisted(timeout: float = 8.0) -> dict[str, Any]:
    """GET allowlisted public pages. Titles and descriptions only. Fail closed."""
    fetched: list[dict[str, Any]] = []
    failed: list[str] = []
    try:
        import httpx
    except ImportError:
        return {"ok": 0, "failed": 0, "docs": [], "error": "httpx missing"}

    headers = {"User-Agent": "FraudForge-research/1.0 (hackathon; defensive intel only)"}
    for url in allowlisted_urls():
        try:
            resp = httpx.get(url, headers=headers, timeout=timeout, follow_redirects=True)
            if resp.status_code >= 400 or "text/html" not in (resp.headers.get("content-type") or ""):
                failed.append(url)
                continue
            preview = _extract_preview(resp.text)
            fetched.append(
                {
                    "id": f"live-{len(fetched)+1}",
                    "title": preview.split(" — ", 1)[0][:180] or url,
                    "date": "live",
                    "url": url,
                    "summary": preview,
                    "families": [],
                    "score": 0.5,
                    "origin": "live",
                }
            )
        except Exception:  # noqa: BLE001
            failed.append(url)
    return {"ok": len(fetched), "failed": len(failed), "docs": fetched, "error": None}


__all__ = ["fetch_allowlisted", "load_corpus", "retrieve", "tokenize"]
