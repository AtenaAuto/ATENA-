#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pipeline automatizado ATENA: objetivo -> web -> análise -> relatório."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
import re
from urllib.parse import quote_plus

import requests

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.atena_browser_agent import AtenaBrowserAgent


def analyze_text(text: str) -> dict:
    tokens = [t.strip(".,:;!?()[]{}\"'").lower() for t in text.split()]
    tokens = [t for t in tokens if len(t) > 3]
    common = Counter(tokens).most_common(15)
    return {
        "chars": len(text),
        "words": len(text.split()),
        "top_terms": common,
    }


def fetch_text_via_http(url: str) -> tuple[bool, str]:
    try:
        resp = requests.get(url, timeout=20)
        if resp.status_code >= 400:
            return False, ""
        html = resp.text
        text = re.sub(r"<[^>]+>", " ", html)
        text = re.sub(r"\\s+", " ", text).strip()
        return True, text
    except Exception:
        return False, ""


def fetch_search_links(query: str, max_links: int = 3) -> list[str]:
    """
    Busca links públicos via DuckDuckGo HTML (sem API key), retornando
    um conjunto pequeno para análise multi-fonte.
    """
    try:
        search_url = f"https://duckduckgo.com/html/?q={quote_plus(query)}"
        resp = requests.get(search_url, timeout=20)
        if resp.status_code >= 400:
            return []
        html = resp.text
        candidates = re.findall(r'href="(https?://[^"]+)"', html)
        links: list[str] = []
        for link in candidates:
            if "duckduckgo.com" in link:
                continue
            if link not in links:
                links.append(link)
            if len(links) >= max_links:
                break
        return links
    except Exception:
        return []


async def run_pipeline(objective: str, base_query: str) -> dict:
    agent = AtenaBrowserAgent()
    query = agent.next_objective_query(objective, base_query)
    target_url = "https://github.com/AtenaAuto/ATENA-"
    screenshot_name: str | None = "atena_pipeline_screenshot.png"
    mode = "browser_agent"
    sources: list[str] = [target_url]

    try:
        await agent.launch(headless=True)
        ok = await agent.navigate(target_url, allow_repeat=True)
        text = await agent.get_text_content() if ok else ""
        await agent.take_screenshot(screenshot_name)
        await agent.close()
    except ModuleNotFoundError:
        mode = "http_fallback"
        screenshot_name = None
        links = fetch_search_links(query, max_links=3)
        if links:
            sources = links
        chunks = []
        ok_any = False
        for src in sources:
            ok_src, text_src = fetch_text_via_http(src)
            if ok_src and text_src:
                ok_any = True
                chunks.append(text_src[:6000])
        ok = ok_any
        text = "\n".join(chunks)
    except Exception:
        mode = "http_fallback"
        screenshot_name = None
        links = fetch_search_links(query, max_links=3)
        if links:
            sources = links
        chunks = []
        ok_any = False
        for src in sources:
            ok_src, text_src = fetch_text_via_http(src)
            if ok_src and text_src:
                ok_any = True
                chunks.append(text_src[:6000])
        ok = ok_any
        text = "\n".join(chunks)

    analysis = analyze_text(text[:12000]) if text else {"chars": 0, "words": 0, "top_terms": []}
    score = 0.85 if ok and analysis["words"] > 20 else 0.35
    agent.record_search_outcome(objective, query, target_url, score, "pipeline_auto_run")

    report = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "objective": objective,
        "query_used": query,
        "target_url": target_url,
        "sources": sources,
        "mode": mode,
        "navigation_ok": ok,
        "analysis": analysis,
        "screenshot": screenshot_name,
    }
    return report


def save_reports(report: dict):
    out_json = ROOT / "atena_evolution" / "pipeline_report.json"
    out_md = ROOT / "atena_evolution" / "pipeline_report.md"
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    terms = "\n".join([f"- {k}: {v}" for k, v in report["analysis"]["top_terms"]])
    md = f"""# ATENA Pipeline Report

- Timestamp: {report['timestamp']}
- Objective: {report['objective']}
- Query usada: `{report['query_used']}`
- URL alvo: {report['target_url']}
- Fontes analisadas: {len(report.get('sources', []))}
- Modo de coleta: {report.get('mode', 'n/a')}
- Navegação OK: {report['navigation_ok']}
- Palavras analisadas: {report['analysis']['words']}

## Fontes
{chr(10).join([f"- {s}" for s in report.get("sources", [])]) if report.get("sources") else "- (sem fontes)"}

## Top termos
{terms if terms else '- (sem termos)'}

## Artefato visual
`{report['screenshot'] or 'não disponível (fallback HTTP)'}`
"""
    out_md.write_text(md, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="ATENA Pipeline")
    parser.add_argument("--objective", default="Gerar inteligência acionável sobre o repositório ATENA")
    parser.add_argument("--query", default="ATENA AGI architecture")
    args = parser.parse_args()

    report = asyncio.run(run_pipeline(args.objective, args.query))
    save_reports(report)
    print("✅ Pipeline concluído.")
    print(f"Objective: {report['objective']}")
    print(f"Query: {report['query_used']}")
    print(f"Words: {report['analysis']['words']}")
    print("Relatórios: atena_evolution/pipeline_report.json e .md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
