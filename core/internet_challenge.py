#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Desafio de pesquisa multi-fonte na internet para validar capacidade operacional."""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from dataclasses import dataclass


@dataclass(frozen=True)
class SourceResult:
    source: str
    ok: bool
    details: dict[str, object]


def _fetch_json(url: str, timeout: int = 15) -> dict:
    with urllib.request.urlopen(url, timeout=timeout) as response:  # nosec - controlled URLs
        return json.loads(response.read().decode("utf-8"))


def run_internet_challenge(topic: str) -> dict[str, object]:
    query = urllib.parse.quote(topic.strip())
    sources: list[SourceResult] = []

    # 1) Wikipedia summary
    try:
        wiki = _fetch_json(f"https://en.wikipedia.org/api/rest_v1/page/summary/{query}")
        sources.append(
            SourceResult(
                source="wikipedia",
                ok=True,
                details={
                    "title": wiki.get("title"),
                    "extract": str(wiki.get("extract", ""))[:280],
                },
            )
        )
    except Exception as exc:  # noqa: BLE001
        sources.append(SourceResult(source="wikipedia", ok=False, details={"error": str(exc)}))

    # 2) GitHub repositories relevance
    try:
        gh = _fetch_json(
            f"https://api.github.com/search/repositories?q={query}&sort=stars&order=desc&per_page=3"
        )
        top = [
            {
                "full_name": item.get("full_name"),
                "stars": item.get("stargazers_count"),
            }
            for item in gh.get("items", [])[:3]
        ]
        sources.append(SourceResult(source="github", ok=True, details={"top_repos": top}))
    except Exception as exc:  # noqa: BLE001
        sources.append(SourceResult(source="github", ok=False, details={"error": str(exc)}))

    # 3) Hacker News relevance via Algolia API
    try:
        hn = _fetch_json(f"https://hn.algolia.com/api/v1/search?query={query}&tags=story&hitsPerPage=3")
        hits = [
            {
                "title": h.get("title"),
                "points": h.get("points"),
            }
            for h in hn.get("hits", [])[:3]
        ]
        sources.append(SourceResult(source="hackernews", ok=True, details={"hits": hits}))
    except Exception as exc:  # noqa: BLE001
        sources.append(SourceResult(source="hackernews", ok=False, details={"error": str(exc)}))

    successful = [s for s in sources if s.ok]
    confidence = round(len(successful) / len(sources), 2) if sources else 0.0

    return {
        "topic": topic,
        "status": "ok" if confidence >= 0.67 else "partial",
        "confidence": confidence,
        "sources": [s.__dict__ for s in sources],
        "recommendation": (
            "Use os resultados para montar análise comparativa e validar consistência entre fontes."
            if confidence >= 0.67
            else "Repita com outro tópico ou amplie timeout/retries para coletar mais sinais."
        ),
    }
