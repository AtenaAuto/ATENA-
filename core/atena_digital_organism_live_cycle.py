#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Ciclo vivo de organismo digital: aprende da internet -> cria -> executa -> testa."""

from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.internet_challenge import run_internet_challenge
from modules.atena_code_module import AtenaCodeModule


def _slugify(text: str) -> str:
    lowered = text.strip().lower()
    safe = re.sub(r"[^a-z0-9_-]+", "-", lowered)
    safe = re.sub(r"-+", "-", safe).strip("-")
    return safe or "atena-project"


def _pick_project_type(learning_payload: dict[str, Any]) -> str:
    sources = {item.get("source"): item for item in learning_payload.get("sources", [])}
    weighted_conf = float(learning_payload.get("weighted_confidence", 0.0))

    npm_q = float(sources.get("npm", {}).get("quality_score", 0.0))
    gh_q = float(sources.get("github", {}).get("quality_score", 0.0))

    if weighted_conf >= 0.70 and (npm_q >= 0.70 or gh_q >= 0.70):
        return "api"
    if weighted_conf >= 0.60:
        return "site"
    return "cli"


def _validate_execution(project_type: str, project_dir: Path) -> dict[str, Any]:
    if project_type == "site":
        index = project_dir / "index.html"
        if not index.exists():
            return {"ok": False, "reason": "index.html ausente"}
        content = index.read_text(encoding="utf-8")
        ok = "<html" in content.lower() and len(content) > 200
        return {"ok": ok, "reason": "estrutura html validada" if ok else "html inválido"}

    main_py = project_dir / "main.py"
    if not main_py.exists():
        return {"ok": False, "reason": "main.py ausente"}

    compile_proc = subprocess.run(
        ["python3", "-m", "py_compile", str(main_py)],
        capture_output=True,
        text=True,
        check=False,
    )
    if compile_proc.returncode != 0:
        return {"ok": False, "reason": "py_compile falhou", "stderr": compile_proc.stderr[-400:]}

    if project_type == "api":
        content = main_py.read_text(encoding="utf-8")
        ok = "@app.get('/health')" in content and "@app.get('/idea')" in content
        return {"ok": ok, "reason": "endpoints health/idea presentes" if ok else "endpoints ausentes"}

    run_proc = subprocess.run(
        ["python3", str(main_py), "ATENA"],
        cwd=str(project_dir),
        capture_output=True,
        text=True,
        check=False,
    )
    ok = run_proc.returncode == 0 and "ATENA" in (run_proc.stdout or "")
    return {
        "ok": ok,
        "reason": "CLI executada com sucesso" if ok else "CLI falhou",
        "stdout_tail": (run_proc.stdout or "")[-300:],
        "stderr_tail": (run_proc.stderr or "")[-300:],
    }


def _persist_learning_memory(root: Path, entry: dict[str, Any]) -> Path:
    evo = root / "atena_evolution"
    evo.mkdir(parents=True, exist_ok=True)
    memory_path = evo / "digital_organism_memory.jsonl"
    with memory_path.open("a", encoding="utf-8") as fp:
        fp.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return memory_path


def _save_cycle_artifacts(root: Path, payload: dict[str, Any]) -> tuple[Path, Path]:
    evo = root / "atena_evolution"
    reports = root / "analysis_reports"
    evo.mkdir(parents=True, exist_ok=True)
    reports.mkdir(parents=True, exist_ok=True)

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    json_path = evo / f"digital_organism_live_cycle_{ts}.json"
    md_path = reports / f"ATENA_Organismo_Digital_Live_Cycle_{date}.md"

    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        f"# ATENA — Live Cycle de Organismo Digital ({date})",
        "",
        f"- Tópico: **{payload['topic']}**",
        f"- Status geral: **{payload['status']}**",
        f"- Projeto criado: **{payload['build']['project_type']} / {payload['build']['project_name']}**",
        f"- Execução/Teste: **{'ok' if payload['execution']['ok'] else 'fail'}**",
        "",
        "## Aprendizado da internet",
        f"- confidence={payload['learning']['confidence']}",
        f"- weighted_confidence={payload['learning']['weighted_confidence']}",
        f"- source_count={payload['learning']['source_count']}",
        "",
        "## Próxima ação autônoma",
        f"- {payload['next_action']}",
    ]
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def run_live_cycle(root: Path, topic: str) -> dict[str, Any]:
    learning = run_internet_challenge(topic)
    project_type = _pick_project_type(learning)

    code_module = AtenaCodeModule(root)
    project_name = f"{_slugify(topic)}-{datetime.now(timezone.utc).strftime('%H%M%S')}"
    build = code_module.build(project_type=project_type, project_name=project_name)

    execution = {
        "ok": False,
        "reason": "build_failed",
    }
    if build.ok:
        execution = _validate_execution(build.project_type, Path(build.output_dir))

    overall_ok = bool(build.ok and execution.get("ok"))
    next_action = (
        "Promover baseline e iniciar iteração com testes mais profundos."
        if overall_ok
        else "Ajustar estratégia de geração e repetir ciclo com tópico mais específico."
    )

    payload = {
        "status": "ok" if overall_ok else "partial",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "topic": topic,
        "learning": {
            "status": learning.get("status"),
            "confidence": learning.get("confidence"),
            "weighted_confidence": learning.get("weighted_confidence"),
            "source_count": learning.get("source_count"),
            "recommendation": learning.get("recommendation"),
        },
        "build": {
            "ok": build.ok,
            "project_type": build.project_type,
            "project_name": build.project_name,
            "output_dir": build.output_dir,
            "message": build.message,
        },
        "execution": execution,
        "next_action": next_action,
    }

    memory_entry = {
        "timestamp": payload["generated_at"],
        "topic": topic,
        "learning": payload["learning"],
        "build": payload["build"],
        "execution": payload["execution"],
        "status": payload["status"],
    }
    memory_path = _persist_learning_memory(root, memory_entry)
    json_path, md_path = _save_cycle_artifacts(root, payload)

    payload["memory_path"] = str(memory_path)
    payload["json_path"] = str(json_path)
    payload["markdown_path"] = str(md_path)
    return payload
