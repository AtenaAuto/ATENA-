#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Missão de análise completa da ATENA com recomendações avançadas de evolução."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _latest_file(pattern: str) -> Path | None:
    files = sorted(ROOT.glob(pattern), key=lambda p: p.stat().st_mtime)
    return files[-1] if files else None


def _load_json(path: Path | None) -> dict[str, object]:
    if path is None or not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _recommendations(module_smoke: dict[str, object], prod_gate: dict[str, object], internet: dict[str, object]) -> list[str]:
    recs: list[str] = []
    if module_smoke.get("status") == "ok":
        recs.append("Expandir smoke suite para cenários de caos (timeouts, quota-limit, API degradada) com retries observáveis.")
    else:
        recs.append("Priorizar estabilização dos módulos com falha antes de novos recursos.")

    prod_approved = bool(prod_gate.get("approved")) or str(prod_gate.get("status", "")).lower() in {"approved", "aprovado", "ok"}
    if prod_approved:
        recs.append("Ativar gate de regressão contínua: bloquear release sem benchmark de latência/custo por missão.")
    else:
        recs.append("Fortalecer produção: corrigir itens do gate e adicionar rollback automatizado por severidade.")

    confidence = float(internet.get("confidence", 0) or 0)
    if confidence >= 0.67:
        recs.append("Adicionar fontes premium de inteligência (arXiv, paperswithcode, NVD) e ranking por confiabilidade temporal.")
    else:
        recs.append("Aumentar robustez de coleta web (retries, anti-403, rotas alternativas de API).")

    recs.append("Criar eval harness avançado com tasks reais: code-repair, red-team prompt-injection e tool-use com auditoria.")
    recs.append("Implementar painel de score operacional: qualidade, custo, latência, taxa de recuperação e risco.")
    return recs


def run() -> tuple[Path, dict[str, object]]:
    module_smoke_path = _latest_file("atena_evolution/module_smoke_suite_*.json")
    prod_gate_path = _latest_file("atena_evolution/production_gate_*.json")
    internet_path = _latest_file("analysis_reports/internet_challenge_*.json")

    module_smoke = _load_json(module_smoke_path)
    prod_gate = _load_json(prod_gate_path)
    internet = _load_json(internet_path)
    recs = _recommendations(module_smoke, prod_gate, internet)
    prod_status = "approved" if (bool(prod_gate.get("approved")) or str(prod_gate.get("status", "")).lower() in {"approved", "aprovado", "ok"}) else "needs-attention"

    now = datetime.now(timezone.utc)
    stamp = now.strftime("%Y-%m-%d")
    out_path = ROOT / "docs" / f"ADVANCED_RECOMMENDATIONS_{stamp}.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        f"# ATENA Advanced Assessment ({stamp})",
        "",
        "## Snapshot",
        f"- Module smoke: `{module_smoke.get('status', 'unknown')}` ({module_smoke_path})",
        f"- Production gate: `{prod_status}` ({prod_gate_path})",
        f"- Internet challenge confidence: `{internet.get('confidence', 'unknown')}` ({internet_path})",
        "",
        "## Recomendações avançadas",
    ]
    for idx, rec in enumerate(recs, start=1):
        lines.append(f"{idx}. {rec}")

    payload = {
        "timestamp": now.isoformat(),
        "inputs": {
            "module_smoke_path": str(module_smoke_path) if module_smoke_path else None,
            "prod_gate_path": str(prod_gate_path) if prod_gate_path else None,
            "internet_path": str(internet_path) if internet_path else None,
        },
        "recommendations": recs,
    }

    lines.extend(["", "## JSON", "```json", json.dumps(payload, ensure_ascii=False, indent=2), "```"])
    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path, payload


def main() -> int:
    parser = argparse.ArgumentParser(description="ATENA Advanced Assessment Mission")
    parser.parse_args()
    out_path, payload = run()
    print("🧠 ATENA Advanced Assessment concluído")
    print(f"recommendations={len(payload.get('recommendations', []))}")
    print(f"report={out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
