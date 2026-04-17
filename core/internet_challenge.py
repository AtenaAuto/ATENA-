#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Desafio de pesquisa multi-fonte na internet para validar capacidade operacional."""

from __future__ import annotations

import json
import os
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from xml.etree import ElementTree


@dataclass(frozen=True)
class SourceResult:
    source: str
    ok: bool
    details: dict[str, object]


SOURCE_WEIGHTS: dict[str, float] = {
    "wikipedia": 0.6,
    "github": 0.9,
    "hackernews": 0.5,
    "arxiv": 1.0,
    "crossref": 1.0,
    "openalex": 0.95,
    "stackoverflow": 0.7,
    "reddit": 0.45,
    "npm": 0.65,
    "europepmc": 0.95,
}


def _fetch_raw(url: str, timeout: int = 15) -> str:
    retries = max(1, int(os.getenv("ATENA_INTERNET_RETRIES", "2")))
    backoff_s = max(0.1, float(os.getenv("ATENA_INTERNET_BACKOFF_S", "0.5")))
    last_err: Exception | None = None

    # Mantém chamada compatível com mocks que esperam URL textual (não Request object).
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(url, timeout=timeout) as response:  # nosec - controlled URLs
                return response.read().decode("utf-8", errors="ignore")
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            if attempt < retries:
                time.sleep(backoff_s * attempt)

    raise RuntimeError(f"falha após {retries} tentativas: {last_err}")


def _fetch_json(url: str, timeout: int = 15) -> dict:
    return json.loads(_fetch_raw(url, timeout=timeout))


def _fetch_text(url: str, timeout: int = 15) -> str:
    return _fetch_raw(url, timeout=timeout)


def _estimate_source_quality(source: str, details: dict[str, object], ok: bool) -> float:
    if not ok:
        return 0.0
    weight = SOURCE_WEIGHTS.get(source, 0.5)
    signals = 0.0

    for key in ("top_repos", "hits", "papers", "works", "questions", "posts", "packages"):
        value = details.get(key)
        if isinstance(value, list):
            signals += min(len(value), 3) / 3

    if details.get("extract"):
        signals += 0.25
    if details.get("error"):
        signals = max(0.0, signals - 0.5)

    # Normaliza para [0,1] e combina com peso de credibilidade da fonte
    normalized = min(1.0, signals)
    return round((0.6 * weight) + (0.4 * normalized), 3)


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
        papers = []
        try:
            root = ElementTree.fromstring(raw)
            ns = {"atom": "http://www.w3.org/2005/Atom"}
            for entry in root.findall("atom:entry", ns)[:3]:
                title = (entry.findtext("atom:title", default="", namespaces=ns) or "").strip()
                papers.append({"title": title})
        except Exception:
            # Fallback para payloads mockados em JSON.
            payload = json.loads(raw)
            for hit in payload.get("hits", [])[:3]:
                papers.append({"title": hit.get("title")})
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
    scored_sources = []
    weighted_total = 0.0
    weighted_ok = 0.0
    for s in sources:
        weight = SOURCE_WEIGHTS.get(s.source, 0.5)
        quality = _estimate_source_quality(s.source, s.details, s.ok)
        weighted_total += weight
        weighted_ok += weight if s.ok else 0.0
        scored_sources.append(
            {
                **s.__dict__,
                "weight": round(weight, 2),
                "quality_score": quality,
            }
        )
    weighted_confidence = round((weighted_ok / weighted_total), 2) if weighted_total else 0.0

    primary_sources = scored_sources[:3]
    high_quality_sources = [
        s["source"] for s in scored_sources if s.get("ok") and float(s.get("quality_score", 0.0)) >= 0.7
    ]
    failed_sources = [s["source"] for s in scored_sources if not s.get("ok")]
    synthesis = {
        "coverage_summary": (
            f"{len(successful)}/{len(sources)} fontes responderam com sucesso "
            f"(alta qualidade: {len(high_quality_sources)})."
        ),
        "high_quality_sources": high_quality_sources,
        "failed_sources": failed_sources,
        "release_risk": (
            "high"
            if weighted_confidence < 0.7 or len(high_quality_sources) < 3
            else "medium"
            if weighted_confidence < 0.85
            else "low"
        ),
        "next_action": (
            "Expandir consulta com palavras-chave mais específicas e validar achados em pelo menos 3 fontes de alta qualidade."
            if weighted_confidence < 0.85
            else "Consolidar síntese final e transformar em plano executável com milestones."
        ),
    }
    difficulty_score = round(
        min(
            1.0,
            (0.5 * (len(failed_sources) / max(1, len(sources))))
            + (0.5 * max(0.0, 1.0 - weighted_confidence)),
        ),
        2,
    )
    return {
        "topic": topic,
        "status": "ok" if weighted_confidence >= 0.65 else "partial",
        "confidence": confidence,
        "weighted_confidence": weighted_confidence,
        "sources": primary_sources,
        "all_sources": scored_sources,
        "source_count": len(primary_sources),
        "all_source_count": len(sources),
        "difficulty_score": difficulty_score,
        "synthesis": synthesis,
        "recommendation": (
            "Use triangulação entre fontes acadêmicas, técnicas e comunidade, priorizando quality_score >= 0.70."
            if weighted_confidence >= 0.65
            else "Amplie timeout/retries e use tópicos mais específicos para aumentar cobertura e qualidade."
        ),
    }
