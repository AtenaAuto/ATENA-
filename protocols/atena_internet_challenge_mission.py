#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Missão de desafio de internet multi-fonte para stressar capacidade da ATENA."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.internet_challenge import run_internet_challenge


def _score_source(source: dict[str, object]) -> int:
    details = source.get("details") if isinstance(source, dict) else {}
    if not isinstance(details, dict):
        details = {}
    size_hint = 0
    for value in details.values():
        if isinstance(value, list):
            size_hint += len(value)
        elif isinstance(value, str) and value.strip():
            size_hint += 1
    return (10 if source.get("ok") else 0) + min(size_hint, 10)


def _build_report(payload: dict[str, object]) -> str:
    sources = payload.get("sources", [])
    ranked: list[tuple[int, dict[str, object]]] = []
    if isinstance(sources, list):
        for src in sources:
            if isinstance(src, dict):
                ranked.append((_score_source(src), src))
    ranked.sort(key=lambda item: item[0], reverse=True)

    lines = [
        "# ATENA Internet Challenge (Extraordinary Mode)",
        "",
        f"**Topic:** {payload.get('topic', '')}",
        f"**Status:** {payload.get('status', '')}",
        f"**Confidence:** {payload.get('confidence', 0)}",
        "",
        "## Ranked Sources",
    ]
    if not ranked:
        lines.append("- Nenhuma fonte retornada.")
    for score, src in ranked:
        lines.append(f"- **{src.get('source', 'unknown')}** | score={score} | ok={src.get('ok')}")

    lines.extend(
        [
            "",
            "## Recommendation",
            str(payload.get("recommendation", "")),
            "",
            "## Raw JSON",
            "```json",
            json.dumps(payload, ensure_ascii=False, indent=2),
            "```",
        ]
    )
    return "\n".join(lines)


def run(topic: str) -> tuple[dict[str, object], Path, Path]:
    payload = run_internet_challenge(topic)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_dir = ROOT / "analysis_reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f"internet_challenge_{timestamp}.json"
    md_path = out_dir / f"internet_challenge_{timestamp}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_build_report(payload), encoding="utf-8")
    return payload, json_path, md_path


def main() -> int:
    parser = argparse.ArgumentParser(description="ATENA Internet Challenge mission")
    parser.add_argument(
        "--topic",
        default="autonomous ai agentic systems safety benchmarks 2026",
        help="Tópico da missão extraordinária na internet",
    )
    args = parser.parse_args()
    payload, json_path, md_path = run(args.topic)
    print("🌐 ATENA Internet Challenge finalizado")
    print(f"status={payload.get('status')} confidence={payload.get('confidence')}")
    print(f"json={json_path}")
    print(f"markdown={md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
