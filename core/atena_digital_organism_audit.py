#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Auditoria reprodutível de maturidade de organismo digital da ATENA."""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class AuditCheck:
    id: str
    pillar: str
    command: list[str]
    weight: float
    description: str


def default_checks() -> list[AuditCheck]:
    return [
        AuditCheck(
            id="doctor",
            pillar="safety-runtime",
            command=["./atena", "doctor"],
            weight=1.5,
            description="Sanidade de runtime, bootstrap e checagens básicas",
        ),
        AuditCheck(
            id="guardian",
            pillar="safety-gate",
            command=["./atena", "guardian"],
            weight=2.0,
            description="Gate de segurança e robustez operacional",
        ),
        AuditCheck(
            id="production-ready",
            pillar="operations",
            command=["./atena", "production-ready"],
            weight=2.0,
            description="Prontidão para produção",
        ),
        AuditCheck(
            id="agi-uplift",
            pillar="cognition-memory",
            command=["./atena", "agi-uplift"],
            weight=2.0,
            description="Memória, continuidade decisória e uplift cognitivo",
        ),
        AuditCheck(
            id="agi-external-validation",
            pillar="external-validation",
            command=["./atena", "agi-external-validation"],
            weight=2.5,
            description="Validação externa independente",
        ),
    ]


def _extract_external_score_from_stdout(stdout: str) -> float | None:
    match = re.search(r"score_0_100=([0-9]+(?:\.[0-9]+)?)", stdout)
    if not match:
        return None
    return float(match.group(1))


def classify_stage(score_0_100: float) -> str:
    if score_0_100 >= 90:
        return "organismo_digital_v1_operacional"
    if score_0_100 >= 75:
        return "organismo_digital_emergente"
    if score_0_100 >= 55:
        return "agente_autonomo_em_transicao"
    return "sistema_automatizado_nao_organico"


def run_digital_organism_audit(root: Path, timeout_seconds: int = 300) -> dict[str, Any]:
    checks = default_checks()
    total_weight = sum(check.weight for check in checks)
    earned_weight = 0.0
    results: list[dict[str, Any]] = []

    for check in checks:
        score_factor = 0.0
        try:
            proc = subprocess.run(
                check.command,
                cwd=str(root),
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
            )
            ok = proc.returncode == 0
            stdout = proc.stdout or ""
            stderr = proc.stderr or ""

            if check.id == "agi-external-validation" and ok:
                ext_score = _extract_external_score_from_stdout(stdout)
                if ext_score is not None:
                    score_factor = max(0.0, min(1.0, ext_score / 100.0))
                else:
                    score_factor = 1.0
            else:
                score_factor = 1.0 if ok else 0.0

            earned_weight += check.weight * score_factor

            results.append(
                {
                    **asdict(check),
                    "ok": ok,
                    "score_factor": round(score_factor, 4),
                    "returncode": proc.returncode,
                    "stdout_tail": stdout[-1200:],
                    "stderr_tail": stderr[-700:],
                }
            )
        except subprocess.TimeoutExpired:
            results.append(
                {
                    **asdict(check),
                    "ok": False,
                    "score_factor": 0.0,
                    "returncode": -1,
                    "stdout_tail": "",
                    "stderr_tail": f"timeout>{timeout_seconds}s",
                }
            )

    score_0_100 = round((earned_weight / total_weight) * 100.0, 2) if total_weight else 0.0
    score_1_10 = round(score_0_100 / 10.0, 2)
    stage = classify_stage(score_0_100)
    verdict = (
        "ATENA atende critérios de organismo digital operacional (v1)."
        if score_0_100 >= 90
        else "ATENA ainda não atende critérios de organismo digital operacional (v1)."
    )

    missing_capabilities = [
        "Autonomia de longo horizonte com metas hierárquicas persistentes.",
        "Governança explícita de identidade/self com invariantes auditáveis.",
        "Metacognição verificável com detecção de autoengano e rollback automático.",
        "Validação externa adversarial contínua (red-team recorrente).",
        "Interoperabilidade multiagente com contratos formais e SLA.",
    ]

    return {
        "status": "ok",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "score_0_100": score_0_100,
        "score_1_10": score_1_10,
        "stage": stage,
        "verdict": verdict,
        "earned_weight": round(earned_weight, 4),
        "total_weight": round(total_weight, 4),
        "checks": results,
        "missing_capabilities": missing_capabilities,
    }


def save_digital_organism_audit(root: Path, payload: dict[str, Any]) -> tuple[Path, Path]:
    evolution = root / "atena_evolution"
    reports = root / "analysis_reports"
    evolution.mkdir(parents=True, exist_ok=True)
    reports.mkdir(parents=True, exist_ok=True)

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    json_path = evolution / f"digital_organism_audit_{ts}.json"
    md_path = reports / f"ATENA_Avaliacao_Organismo_Digital_Automatica_{date}.md"

    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        f"# ATENA — Auditoria Automática de Organismo Digital ({date})",
        "",
        f"- Score (0-100): **{payload['score_0_100']}**",
        f"- Score (1-10): **{payload['score_1_10']}**",
        f"- Estágio: **{payload['stage']}**",
        f"- Veredito: **{payload['verdict']}**",
        "",
        "## Checks executados",
    ]

    for item in payload["checks"]:
        icon = "✅" if item["ok"] else "❌"
        cmd = " ".join(item["command"])
        lines.append(
            f"- {icon} `{item['id']}` ({item['pillar']}) w={item['weight']} fator={item['score_factor']} :: `{cmd}`"
        )

    lines.extend(["", "## O que falta para maior maturidade"])
    for gap in payload["missing_capabilities"]:
        lines.append(f"- {gap}")

    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path
