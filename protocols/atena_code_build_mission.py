#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Missão de programação: ATENA constrói app/site/software automaticamente."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.atena_code_module import AtenaCodeModule


def main() -> int:
    parser = argparse.ArgumentParser(description="ATENA Code Build Mission")
    parser.add_argument("--type", dest="project_type", choices=["site", "api", "cli"], default="site")
    parser.add_argument("--name", dest="project_name", default="atena_app")
    args = parser.parse_args()

    builder = AtenaCodeModule(ROOT)
    result = builder.build(args.project_type, args.project_name)

    if result.ok:
        print("🧠💻 ATENA Code Module")
        print(f"Projeto: {result.project_name}")
        print(f"Tipo: {result.project_type}")
        print(f"Saída: {result.output_dir}")
        print("Status: sucesso")
        return 0

    print(f"❌ Falha: {result.message}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
