#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Missão: ciclo vivo (aprende na internet, cria, executa e testa)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.atena_digital_organism_live_cycle import run_live_cycle


def main() -> int:
    parser = argparse.ArgumentParser(description="Executa live cycle de organismo digital")
    parser.add_argument("--topic", default="autonomous ai engineering", help="Tópico para aprendizado na internet")
    args = parser.parse_args()

    payload = run_live_cycle(ROOT, topic=args.topic)
    print("🧠⚙️🧪 ATENA Digital Organism Live Cycle")
    print(f"topic={payload['topic']}")
    print(f"status={payload['status']}")
    print(f"project_type={payload['build']['project_type']}")
    print(f"build_ok={payload['build']['ok']}")
    print(f"execution_ok={payload['execution']['ok']}")
    print(f"memory={payload['memory_path']}")
    print(f"json={payload['json_path']}")
    print(f"markdown={payload['markdown_path']}")
    return 0 if payload["status"] == "ok" else 2


if __name__ == "__main__":
    raise SystemExit(main())
