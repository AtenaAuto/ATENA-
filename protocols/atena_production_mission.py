#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ATENA Ω — Production Mission: gate final de produção."""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def run_cmd(cmd: list[str], timeout: int = 300) -> dict:
    proc = subprocess.run(
        cmd,
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    return {
        "command": " ".join(cmd),
        "returncode": proc.returncode,
        "stdout": proc.stdout[-8000:],
        "stderr": proc.stderr[-4000:],
        "ok": proc.returncode == 0,
    }


def main() -> int:
    checks = [
        run_cmd(["./atena", "doctor"], timeout=240),
        run_cmd(["./atena", "guardian"], timeout=300),
    ]

    ok = all(c["ok"] for c in checks)
    now = datetime.now(timezone.utc)
    stamp = now.strftime("%Y-%m-%d")

    docs_dir = ROOT / "docs"
    evo_dir = ROOT / "atena_evolution"
    docs_dir.mkdir(parents=True, exist_ok=True)
    evo_dir.mkdir(parents=True, exist_ok=True)

    md_path = docs_dir / f"PRODUCTION_GATE_{stamp}.md"
    json_path = evo_dir / f"production_gate_{now.strftime('%Y%m%d_%H%M%S')}.json"

    md_lines = [
        f"# Production Gate — {stamp}",
        "",
        f"- Gate final: **{'APROVADO' if ok else 'REPROVADO'}**",
        "",
        "## Checks executados",
    ]
    for c in checks:
        status = "✅" if c["ok"] else "❌"
        md_lines.append(f"- {status} `{c['command']}` (rc={c['returncode']})")
    md_lines.append("")
    md_lines.append("## Política recomendada")
    md_lines.append("Permitir release apenas se `doctor` e `guardian` passarem no mesmo commit.")

    md_path.write_text("\n".join(md_lines), encoding="utf-8")

    payload = {
        "generated_at": now.isoformat(),
        "approved": ok,
        "checks": checks,
        "report_markdown": str(md_path.relative_to(ROOT)),
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print("🚦 ATENA Production Gate")
    print(f"Status: {'APROVADO' if ok else 'REPROVADO'}")
    for c in checks:
        print(f"- {'OK' if c['ok'] else 'FAIL'}: {c['command']} (rc={c['returncode']})")
    print(f"Relatório: {md_path.relative_to(ROOT)}")
    print(f"Artefato: {json_path.relative_to(ROOT)}")

    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
