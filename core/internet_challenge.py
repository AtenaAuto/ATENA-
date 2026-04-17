#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Desafio de pesquisa multi-fonte na internet para validar capacidade operacional."""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from dataclasses import dataclass
from xml.etree import ElementTree


@dataclass(frozen=True)
class SourceResult:
    source: str
    ok: bool
    details: dict[str, object]


def _fetch_json(url: str, timeout: int = 15) -> dict:
    req = urllib.request.Request(
        url=url,
        headers={"User-Agent": "ATENA-Internet-Challenge/1.0 (+https://github.com/AtenaAuto/ATENA-)"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:  # nosec - controlled URLs
        return json.loads(response.read().decode("utf-8"))


def _fetch_text(url: str, timeout: int = 15) -> str:
    req = urllib.request.Request(
        url=url,
        headers={"User-Agent": "ATENA-Internet-Challenge/1.0 (+https://github.com/AtenaAuto/ATENA-)"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:  # nosec - controlled URLs
        return response.read().decode("utf-8", errors="ignore")


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

    # 4) arXiv papers
    try:
        raw = _fetch_text(
            f"https://export.arxiv.org/api/query?search_query=all:{query}&start=0&max_results=3"
        )
        root = ElementTree.fromstring(raw)
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        papers = []
        for entry in root.findall("atom:entry", ns)[:3]:
            title = (entry.findtext("atom:title", default="", namespaces=ns) or "").strip()
            papers.append({"title": title})
        sources.append(SourceResult(source="arxiv", ok=True, details={"papers": papers}))
    except Exception as exc:  # noqa: BLE001
        sources.append(SourceResult(source="arxiv", ok=False, details={"error": str(exc)}))

    # 5) Crossref works
    try:
        crossref = _fetch_json(
            f"https://api.crossref.org/works?query={query}&rows=3&select=title,DOI,is-referenced-by-count"
        )
        items = []
        for item in crossref.get("message", {}).get("items", [])[:3]:
            title = ""
            if isinstance(item.get("title"), list) and item["title"]:
                title = str(item["title"][0])
            items.append(
                {
                    "title": title,
                    "doi": item.get("DOI"),
                    "citations": item.get("is-referenced-by-count"),
                }
            )
        sources.append(SourceResult(source="crossref", ok=True, details={"works": items}))
    except Exception as exc:  # noqa: BLE001
        sources.append(SourceResult(source="crossref", ok=False, details={"error": str(exc)}))

    # 6) OpenAlex works
    try:
        openalex = _fetch_json(
            f"https://api.openalex.org/works?search={query}&per-page=3&select=display_name,cited_by_count"
        )
        works = [
            {
                "title": w.get("display_name"),
                "citations": w.get("cited_by_count"),
            }
            for w in openalex.get("results", [])[:3]
        ]
        sources.append(SourceResult(source="openalex", ok=True, details={"works": works}))
    except Exception as exc:  # noqa: BLE001
        sources.append(SourceResult(source="openalex", ok=False, details={"error": str(exc)}))

    # 7) StackExchange Q&A signals
    try:
        stack = _fetch_json(
            "https://api.stackexchange.com/2.3/search/advanced"
            f"?order=desc&sort=votes&q={query}&site=stackoverflow&pagesize=3"
        )
        questions = [
            {
                "title": q.get("title"),
                "score": q.get("score"),
            }
            for q in stack.get("items", [])[:3]
        ]
        sources.append(SourceResult(source="stackoverflow", ok=True, details={"questions": questions}))
    except Exception as exc:  # noqa: BLE001
        sources.append(SourceResult(source="stackoverflow", ok=False, details={"error": str(exc)}))

    # 8) Reddit community trends
    try:
        reddit = _fetch_json(f"https://www.reddit.com/search.json?q={query}&limit=3&sort=relevance")
        posts = [
            {
                "title": c.get("data", {}).get("title"),
                "score": c.get("data", {}).get("score"),
            }
            for c in reddit.get("data", {}).get("children", [])[:3]
        ]
        sources.append(SourceResult(source="reddit", ok=True, details={"posts": posts}))
    except Exception as exc:  # noqa: BLE001
        sources.append(SourceResult(source="reddit", ok=False, details={"error": str(exc)}))

    # 9) npm package ecosystem
    try:
        npm = _fetch_json(f"https://registry.npmjs.org/-/v1/search?text={query}&size=3")
        packages = [
            {
                "name": obj.get("package", {}).get("name"),
                "version": obj.get("package", {}).get("version"),
            }
            for obj in npm.get("objects", [])[:3]
        ]
        sources.append(SourceResult(source="npm", ok=True, details={"packages": packages}))
    except Exception as exc:  # noqa: BLE001
        sources.append(SourceResult(source="npm", ok=False, details={"error": str(exc)}))

    # 10) Europe PMC biomedical/research signals
    try:
        epmc = _fetch_json(
            f"https://www.ebi.ac.uk/europepmc/webservices/rest/search?query={query}&format=json&pageSize=3"
        )
        papers = [
            {
                "title": item.get("title"),
                "source": item.get("journalTitle") or item.get("source"),
            }
            for item in epmc.get("resultList", {}).get("result", [])[:3]
        ]
        sources.append(SourceResult(source="europepmc", ok=True, details={"papers": papers}))
    except Exception as exc:  # noqa: BLE001
        sources.append(SourceResult(source="europepmc", ok=False, details={"error": str(exc)}))

    successful = [s for s in sources if s.ok]
    confidence = round(len(successful) / len(sources), 2) if sources else 0.0

    return {
        "topic": topic,
        "status": "ok" if confidence >= 0.6 else "partial",
        "confidence": confidence,
        "sources": [s.__dict__ for s in sources],
        "recommendation": (
            "Use triangulação entre fontes acadêmicas, técnicas e comunidade para reduzir viés."
            if confidence >= 0.6
            else "Repita com outro tópico, retries e timeout maior para coletar sinais mais consistentes."
        ),
    }
