#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Atena Code Module: gera apps/sites/software iniciais de forma autônoma."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

ProjectType = Literal["site", "api", "cli"]


@dataclass
class BuildResult:
    ok: bool
    project_type: str
    project_name: str
    output_dir: str
    message: str


class AtenaCodeModule:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.generated_root = self.root / "atena_evolution" / "generated_apps"
        self.generated_root.mkdir(parents=True, exist_ok=True)

    def build(self, project_type: ProjectType, project_name: str) -> BuildResult:
        safe_name = "".join(ch for ch in project_name if ch.isalnum() or ch in ("-", "_")).strip("-_")
        if not safe_name:
            return BuildResult(False, project_type, project_name, "", "Nome de projeto inválido")

        out = self.generated_root / safe_name
        out.mkdir(parents=True, exist_ok=True)

        if project_type == "site":
            self._build_site(out, safe_name)
        elif project_type == "api":
            self._build_api(out, safe_name)
        elif project_type == "cli":
            self._build_cli(out, safe_name)
        else:
            return BuildResult(False, project_type, project_name, str(out), "Tipo de projeto inválido")

        return BuildResult(True, project_type, safe_name, str(out), "Projeto gerado com sucesso")

    def _build_site(self, out: Path, name: str) -> None:
        (out / "index.html").write_text(
            f"""<!doctype html>
<html lang=\"pt-BR\"> 
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width,initial-scale=1\" />
  <title>{name} — Site gerado pela ATENA</title>
  <link rel=\"stylesheet\" href=\"style.css\" />
</head>
<body>
  <main>
    <h1>{name}</h1>
    <p>Site inicial gerado automaticamente pelo módulo de programação da ATENA.</p>
    <button id=\"helloBtn\">Testar interação</button>
    <p id=\"output\"></p>
  </main>
  <script src=\"app.js\"></script>
</body>
</html>
""",
            encoding="utf-8",
        )
        (out / "style.css").write_text(
            "body{font-family:system-ui;background:#0f172a;color:#e2e8f0;display:grid;place-items:center;min-height:100vh;}main{max-width:760px;padding:24px;border:1px solid #334155;border-radius:12px;}button{padding:10px 14px;border-radius:8px;border:none;cursor:pointer;}",
            encoding="utf-8",
        )
        (out / "app.js").write_text(
            "document.getElementById('helloBtn').addEventListener('click',()=>{document.getElementById('output').textContent='✅ ATENA gerou e executou a base do site com sucesso!';});",
            encoding="utf-8",
        )

    def _build_api(self, out: Path, name: str) -> None:
        (out / "requirements.txt").write_text("fastapi\nuvicorn\n", encoding="utf-8")
        (out / "main.py").write_text(
            f"""from fastapi import FastAPI

app = FastAPI(title=\"{name}\")

@app.get('/health')
def health():
    return {{'status':'ok','service':'{name}'}}

@app.get('/idea')
def idea():
    return {{'idea':'ATENA recomenda adicionar fila assíncrona + observabilidade por traces'}}
""",
            encoding="utf-8",
        )

    def _build_cli(self, out: Path, name: str) -> None:
        (out / "main.py").write_text(
            f"""#!/usr/bin/env python3
import argparse


def main():
    parser = argparse.ArgumentParser(prog='{name}', description='CLI gerada pela ATENA')
    parser.add_argument('nome', nargs='?', default='mundo')
    args = parser.parse_args()
    print(f'Olá, {{args.nome}}! Software CLI {name} criado pela ATENA ✅')


if __name__ == '__main__':
    main()
""",
            encoding="utf-8",
        )
