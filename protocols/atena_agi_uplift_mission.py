#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Missão de elevação AGI-like da ATENA."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.atena_agi_uplift import (
    ContinuousEvaluator,
    GeneralizationRouter,
    LongTermMemoryEngine,
    MultiStepPlanner,
    SecurityAuditor,
    SelfCorrectionEngine,
)

def main() -> int:
    evolution = ROOT / "atena_evolution"
    evolution.mkdir(parents=True, exist_ok=True)

    memory = LongTermMemoryEngine(ROOT)
    evaluator = ContinuousEvaluator(ROOT)
    planner = MultiStepPlanner()
    security = SecurityAuditor(ROOT)
    router = GeneralizationRouter()
    autocorrect = SelfCorrectionEngine()

    memory.remember_decision(
        objective="reduzir falhas no deploy",
        decision="adicionar regressão diária e bloqueio quando cair score",
        outcome="melhoria de estabilidade",
        tags=["deploy", "benchmark", "stability"],
    )
    recalled = memory.semantic_recall("benchmark deploy estabilidade", top_k=3)

    evaluator.record_score(0.81, date=datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    regression = evaluator.regression_guard(min_drop=0.08, window=3)
    deploy_gate = evaluator.enforce_deploy_gate(regression)
    benchmark_run = evaluator.run_benchmark_commands(
        commands=[[sys.executable, "-m", "py_compile", "core/atena_agi_uplift.py"]],
        cwd=ROOT,
    )

    plan_exec = planner.execute(
        objective="elevar confiabilidade operacional",
        step_executor=lambda step: (True, f"executado: {step}"),
        rollback=lambda step: f"rollback aplicado para {step}",
    )

    sec_check = security.can_execute("tier2", approved=True)
    sec_audit = security.audit(
        action="deploy-main",
        tier="tier2",
        approved=True,
        result="allowed" if sec_check else "blocked",
    )

    generalization = {
        "dados": router.expand_plan("Criar pipeline ETL com métricas de qualidade"),
        "estrategia": router.expand_plan("Criar roadmap e pricing de lançamento"),
        "documentacao": router.expand_plan("Escrever runbook de incidentes"),
        "infra": router.expand_plan("Melhorar observability e deploy SRE"),
        "dev": router.expand_plan("Refactor de módulo Python com testes"),
    }
    self_correction = autocorrect.run_iterative(
        test_cmd=[sys.executable, "-c", "print('ok')"],
        patch_cmds=[[sys.executable, "-c", "print('patch-attempt')"]],
        rollback_cmd=[sys.executable, "-c", "print('rollback')"],
        cwd=ROOT,
    )

    payload = {
        "status": "ok",
        "recalled_memories": recalled,
        "decision_history_tail": memory.decision_history(limit=5),
        "regression_guard": regression,
        "deploy_gate": deploy_gate,
        "benchmark_run": benchmark_run,
        "plan_execution": plan_exec,
        "self_correction": self_correction,
        "security": {"can_execute_tier2": sec_check, "audit": sec_audit},
        "generalization_samples": generalization,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    out = evolution / f"agi_uplift_report_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print("🧠 ATENA AGI Uplift Mission")
    print("status=ok")
    print(f"report={out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
