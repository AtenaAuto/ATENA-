#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Desafio de pesquisa multi-fonte na internet para validar capacidade operacional."""

from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from urllib.error import HTTPError
from dataclasses import dataclass
from xml.etree import ElementTree as ET


@dataclass(frozen=True)
class SourceResult:
    source: str
    ok: bool
    details: dict[str, object]


def _fetch_json(url: str, timeout: int = 15) -> dict:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "ATENA/3.2 (+https://github.com/AtenaAuto/ATENA-)",
            "Accept": "application/json",
        },
    )
    for attempt in range(2):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:  # nosec - controlled URLs
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            if exc.code == 403 and attempt == 0:
                time.sleep(0.4)
                continue
            raise
    return {}


def _fetch_text(url: str, timeout: int = 15) -> str:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "ATENA/3.2 (+https://github.com/AtenaAuto/ATENA-)",
            "Accept": "application/json,text/plain,application/atom+xml",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:  # nosec - controlled URLs
        return response.read().decode("utf-8", errors="replace")


def _compact_query(topic: str) -> str:
    tokens = [t.strip(".,:;!?()[]{}\"'").lower() for t in topic.split()]
    stop = {
        "the",
        "of",
        "and",
        "in",
        "on",
        "for",
        "to",
        "with",
        "state",
        "readiness",
        "reliability",
        "safety",
        "hardening",
        "production",
    }
    filtered = [t for t in tokens if t and t not in stop and len(t) > 2]
    return " ".join(filtered[:6]) or topic


def run_internet_challenge(topic: str) -> dict[str, object]:
    compact_topic = _compact_query(topic.strip())
    query = urllib.parse.quote(topic.strip())
    compact_query = urllib.parse.quote(compact_topic)
    sources: list[SourceResult] = []

    # 1) Wikipedia summary
    try:
        wiki = _fetch_json(f"https://en.wikipedia.org/api/rest_v1/page/summary/{query}")
        if not wiki.get("extract"):
            raise ValueError("Wikipedia summary vazio para query direta")
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
        try:
            search = _fetch_json(
                f"https://en.wikipedia.org/w/api.php?action=opensearch&search={query}&limit=1&namespace=0&format=json"
            )
            title = ""
            if isinstance(search, list) and len(search) >= 2 and isinstance(search[1], list) and search[1]:
                title = str(search[1][0]).strip()
            if title:
                title_q = urllib.parse.quote(title)
                wiki = _fetch_json(f"https://en.wikipedia.org/api/rest_v1/page/summary/{title_q}")
                sources.append(
                    SourceResult(
                        source="wikipedia",
                        ok=True,
                        details={
                            "title": wiki.get("title") or title,
                            "extract": str(wiki.get("extract", ""))[:280],
                            "fallback_search": True,
                        },
                    )
                )
            else:
                sources.append(SourceResult(source="wikipedia", ok=False, details={"error": str(exc)}))
        except Exception as fallback_exc:  # noqa: BLE001
            sources.append(
                SourceResult(
                    source="wikipedia",
                    ok=False,
                    details={"error": str(exc), "fallback_error": str(fallback_exc)},
                )
            )

    # 2) GitHub repositories relevance
    try:
        gh = _fetch_json(
            f"https://api.github.com/search/repositories?q={compact_query}&sort=stars&order=desc&per_page=3"
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
        hn = _fetch_json(f"https://hn.algolia.com/api/v1/search?query={compact_query}&tags=story&hitsPerPage=3")
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

    # 4) arXiv relevance via Atom feed
    try:
        xml_text = _fetch_text(
            f"http://export.arxiv.org/api/query?search_query=all:{compact_query}&start=0&max_results=3"
        )
        root = ET.fromstring(xml_text)
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        entries = root.findall("atom:entry", ns)
        papers = []
        for entry in entries[:3]:
            title = (entry.findtext("atom:title", default="", namespaces=ns) or "").strip()
            papers.append({"title": title[:180]})
        sources.append(SourceResult(source="arxiv", ok=True, details={"papers": papers}))
    except Exception as exc:  # noqa: BLE001
        sources.append(SourceResult(source="arxiv", ok=False, details={"error": str(exc)}))

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
