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


async def run_pipeline(objective: str, base_query: str) -> dict:
    agent = AtenaBrowserAgent()
    query = agent.next_objective_query(objective, base_query)
    target_url = "https://github.com/AtenaAuto/ATENA-"
    screenshot_name: str | None = "atena_pipeline_screenshot.png"
    mode = "browser_agent"

    try:
        await agent.launch(headless=True)
        ok = await agent.navigate(target_url, allow_repeat=True)
        text = await agent.get_text_content() if ok else ""
        await agent.take_screenshot(screenshot_name)
        await agent.close()
    except ModuleNotFoundError:
        mode = "http_fallback"
        screenshot_name = None
        ok, text = fetch_text_via_http(target_url)
    except Exception:
        mode = "http_fallback"
        screenshot_name = None
        ok, text = fetch_text_via_http(target_url)

    analysis = analyze_text(text[:12000]) if text else {"chars": 0, "words": 0, "top_terms": []}
    score = 0.85 if ok and analysis["words"] > 20 else 0.35
    agent.record_search_outcome(objective, query, target_url, score, "pipeline_auto_run")

    report = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "objective": objective,
        "query_used": query,
        "target_url": target_url,
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
- Modo de coleta: {report.get('mode', 'n/a')}
- Navegação OK: {report['navigation_ok']}
- Palavras analisadas: {report['analysis']['words']}

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
