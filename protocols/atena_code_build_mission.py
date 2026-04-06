#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Missão de programação: ATENA constrói app/site/software automaticamente."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.atena_code_module import AtenaCodeModule


def iter_project_files(output_dir: Path) -> Iterable[Path]:
    for path in sorted(output_dir.rglob("*")):
        if path.is_file():
            yield path


def print_generated_code(output_dir: Path) -> None:
    print("\n📦 Código completo gerado pela ATENA:")
    printed = 0
    for file_path in iter_project_files(output_dir):
        try:
            content = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        rel = file_path.relative_to(output_dir)
        print("\n" + "=" * 78)
        print(f"📄 {rel}")
        print("=" * 78)
        print(content.rstrip())
        printed += 1
    if printed == 0:
        print("- (nenhum arquivo textual encontrado para exibir)")


def main() -> int:
    parser = argparse.ArgumentParser(description="ATENA Code Build Mission")
    parser.add_argument("--type", dest="project_type", choices=["site", "api", "cli"], default="site")
    parser.add_argument("--name", dest="project_name", default="atena_app")
    parser.add_argument(
        "--template",
        choices=["basic", "landing-page", "portfolio", "dashboard", "blog"],
        default="basic",
        help="Template visual para tipo site",
    )
    args = parser.parse_args()

    builder = AtenaCodeModule(ROOT)
    result = builder.build(args.project_type, args.project_name, template=args.template)

    if result.ok:
        print("🧠💻 ATENA Code Module")
        print(f"Projeto: {result.project_name}")
        print(f"Tipo: {result.project_type}")
        print(f"Template: {result.template}")
        print(f"Saída: {result.output_dir}")
        print("Status: sucesso")
        print_generated_code(Path(result.output_dir))
        return 0

    print(f"❌ Falha: {result.message}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
