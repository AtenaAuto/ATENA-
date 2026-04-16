#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Camada de evolução AGI-like: memória, avaliação, planejamento, autocorreção, segurança e generalização."""

from __future__ import annotations

import json
import math
import re
import subprocess
import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional


def _tokenize(text: str) -> list[str]:
    return [tok for tok in re.findall(r"[a-zA-Z0-9_]+", text.lower()) if len(tok) > 1]


def _cosine(a: dict[str, float], b: dict[str, float]) -> float:
    if not a or not b:
        return 0.0
    keys = set(a) | set(b)
    num = sum(a.get(k, 0.0) * b.get(k, 0.0) for k in keys)
    den_a = math.sqrt(sum(v * v for v in a.values()))
    den_b = math.sqrt(sum(v * v for v in b.values()))
    if den_a == 0 or den_b == 0:
        return 0.0
    return num / (den_a * den_b)


def _to_vector(text: str) -> dict[str, float]:
    vec: dict[str, float] = {}
    for tok in _tokenize(text):
        vec[tok] = vec.get(tok, 0.0) + 1.0
    return vec


class LongTermMemoryEngine:
    """Memória de longo prazo com recuperação semântica por similaridade vetorial leve."""

    def __init__(self, root: Path):
        self.root = root
        self.memory_path = self.root / "atena_evolution" / "long_term_memory.jsonl"
        self.memory_path.parent.mkdir(parents=True, exist_ok=True)

    def _rows(self) -> list[dict[str, Any]]:
        if not self.memory_path.exists():
            return []
        rows: list[dict[str, Any]] = []
        for line in self.memory_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
        return rows

    def remember_decision(self, objective: str, decision: str, outcome: str, tags: list[str] | None = None) -> dict[str, Any]:
        previous = self._rows()[-1] if self._rows() else None
        decision_id = hashlib.sha1(f"{objective}|{decision}|{datetime.now(timezone.utc).isoformat()}".encode("utf-8")).hexdigest()[:12]
        item = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "decision_id": decision_id,
            "parent_decision_id": previous.get("decision_id") if previous else None,
            "objective": objective,
            "decision": decision,
            "outcome": outcome,
            "tags": tags or [],
            "combined_text": f"{objective} {decision} {outcome} {' '.join(tags or [])}".strip(),
        }
        with self.memory_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
        return item

    def semantic_recall(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        rows = self._rows()
        if not rows:
            return []
        qv = _to_vector(query)
        scored: list[tuple[float, dict[str, Any]]] = []
        for item in rows:
            score = _cosine(qv, _to_vector(str(item.get("combined_text", ""))))
            if score > 0:
                scored.append((score, item))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [{**itm, "semantic_score": round(score, 4)} for score, itm in scored[:top_k]]

    def decision_history(self, limit: int = 20) -> list[dict[str, Any]]:
        rows = self._rows()
        return rows[-limit:]


class ContinuousEvaluator:
    """Benchmark diário com regressão e bloqueio de deploy."""

    def __init__(self, root: Path):
        self.root = root
        self.score_path = self.root / "atena_evolution" / "daily_benchmark_scores.json"
        self.score_path.parent.mkdir(parents=True, exist_ok=True)

    def _load(self) -> list[dict[str, Any]]:
        if not self.score_path.exists():
            return []
        return json.loads(self.score_path.read_text(encoding="utf-8"))

    def _save(self, rows: list[dict[str, Any]]) -> None:
        self.score_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")

    def record_score(self, score: float, date: Optional[str] = None) -> dict[str, Any]:
        rows = self._load()
        entry = {
            "date": date or datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "score": float(score),
        }
        rows = [r for r in rows if r.get("date") != entry["date"]]
        rows.append(entry)
        rows.sort(key=lambda x: x["date"])
        self._save(rows)
        return entry

    def regression_guard(self, min_drop: float = 0.08, window: int = 3) -> dict[str, Any]:
        rows = self._load()
        if len(rows) < window + 1:
            return {"status": "insufficient_history", "block_deploy": False}
        latest = rows[-1]["score"]
        baseline = sum(r["score"] for r in rows[-(window + 1):-1]) / window
        drop_ratio = (baseline - latest) / baseline if baseline > 0 else 0.0
        block = drop_ratio >= min_drop
        return {
            "status": "regression" if block else "ok",
            "latest": latest,
            "baseline": round(baseline, 4),
            "drop_ratio": round(drop_ratio, 4),
            "block_deploy": block,
        }

    def run_benchmark_commands(self, commands: list[list[str]], cwd: Path) -> dict[str, Any]:
        results: list[dict[str, Any]] = []
        for cmd in commands:
            proc = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, check=False)
            results.append(
                {
                    "cmd": " ".join(cmd),
                    "ok": proc.returncode == 0,
                    "returncode": proc.returncode,
                }
            )
        ok_count = sum(1 for r in results if r["ok"])
        score = ok_count / len(results) if results else 0.0
        self.record_score(score)
        return {"score": score, "ok_count": ok_count, "total": len(results), "results": results}

    def enforce_deploy_gate(self, guard: dict[str, Any]) -> dict[str, Any]:
        gate_path = self.root / "atena_evolution" / "deploy_gate_status.json"
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "blocked": bool(guard.get("block_deploy", False)),
            "reason": guard.get("status", "unknown"),
            "guard": guard,
        }
        gate_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return payload


@dataclass
class StepResult:
    step: str
    ok: bool
    details: str


class MultiStepPlanner:
    """Planejamento multi-etapas com validação e rollback."""

    DEFAULT_STEPS = ["diagnóstico", "implementação", "validação", "entrega"]

    def decompose_objective(self, objective: str) -> list[str]:
        base = [
            f"coletar contexto para '{objective}'",
            f"quebrar '{objective}' em subtarefas mensuráveis",
            f"definir validação objetiva para '{objective}'",
        ]
        if any(k in objective.lower() for k in ["deploy", "produção", "production"]):
            base.append("validar rollback e mitigação de risco")
        return base

    def plan(self, objective: str) -> list[str]:
        steps = [f"{s}: {objective}" for s in self.DEFAULT_STEPS]
        return self.decompose_objective(objective) + steps

    def execute(
        self,
        objective: str,
        step_executor: Callable[[str], tuple[bool, str]],
        rollback: Callable[[str], str],
    ) -> dict[str, Any]:
        steps = self.plan(objective)
        results: list[StepResult] = []
        for step in steps:
            ok, details = step_executor(step)
            results.append(StepResult(step=step, ok=ok, details=details))
            if not ok:
                rb = rollback(step)
                return {
                    "status": "failed",
                    "results": [r.__dict__ for r in results],
                    "rollback": rb,
                }
        return {"status": "ok", "results": [r.__dict__ for r in results], "rollback": None}


class SelfCorrectionEngine:
    """Auto-correção guiada por testes com patch e rollback."""

    def run(self, test_cmd: list[str], patch_cmd: list[str], rollback_cmd: list[str], cwd: Path) -> dict[str, Any]:
        first = subprocess.run(test_cmd, cwd=str(cwd), capture_output=True, text=True, check=False)
        if first.returncode == 0:
            return {"status": "ok", "phase": "initial-tests-pass"}

        patch = subprocess.run(patch_cmd, cwd=str(cwd), capture_output=True, text=True, check=False)
        second = subprocess.run(test_cmd, cwd=str(cwd), capture_output=True, text=True, check=False)
        if patch.returncode == 0 and second.returncode == 0:
            return {"status": "ok", "phase": "patched-and-validated"}

        rollback = subprocess.run(rollback_cmd, cwd=str(cwd), capture_output=True, text=True, check=False)
        return {
            "status": "failed",
            "phase": "rollback",
            "test_returncode": second.returncode,
            "rollback_returncode": rollback.returncode,
        }

    def run_iterative(self, test_cmd: list[str], patch_cmds: list[list[str]], rollback_cmd: list[str], cwd: Path) -> dict[str, Any]:
        first = subprocess.run(test_cmd, cwd=str(cwd), capture_output=True, text=True, check=False)
        if first.returncode == 0:
            return {"status": "ok", "attempts": 0, "phase": "initial-tests-pass"}
        attempts = 0
        for patch_cmd in patch_cmds:
            attempts += 1
            subprocess.run(patch_cmd, cwd=str(cwd), capture_output=True, text=True, check=False)
            verify = subprocess.run(test_cmd, cwd=str(cwd), capture_output=True, text=True, check=False)
            if verify.returncode == 0:
                return {"status": "ok", "attempts": attempts, "phase": "patched-and-validated"}
        rb = subprocess.run(rollback_cmd, cwd=str(cwd), capture_output=True, text=True, check=False)
        return {"status": "failed", "attempts": attempts, "phase": "rollback", "rollback_returncode": rb.returncode}


class SecurityAuditor:
    """Tiers rígidos + auditoria de ações críticas."""

    TIERS = {
        "tier0": {"desc": "read-only"},
        "tier1": {"desc": "safe local writes"},
        "tier2": {"desc": "high-impact ops"},
    }

    def __init__(self, root: Path):
        self.root = root
        self.audit_path = self.root / "atena_evolution" / "critical_actions_audit.jsonl"
        self.audit_path.parent.mkdir(parents=True, exist_ok=True)

    def _last_hash(self) -> str:
        if not self.audit_path.exists():
            return "GENESIS"
        lines = [ln for ln in self.audit_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
        if not lines:
            return "GENESIS"
        last = json.loads(lines[-1])
        return str(last.get("hash", "GENESIS"))

    def can_execute(self, tier: str, approved: bool) -> bool:
        if tier not in self.TIERS:
            return False
        if tier == "tier2":
            return approved
        return True

    def audit(self, action: str, tier: str, approved: bool, result: str) -> dict[str, Any]:
        prev_hash = self._last_hash()
        item = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": action,
            "tier": tier,
            "approved": approved,
            "result": result,
            "prev_hash": prev_hash,
        }
        item["hash"] = hashlib.sha256(json.dumps(item, sort_keys=True).encode("utf-8")).hexdigest()
        with self.audit_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
        return item


class GeneralizationRouter:
    """Expansão de domínios além de dev/terminal."""

    DOMAINS = {
        "dados": ["dataset", "sql", "analytics", "etl", "métrica"],
        "estrategia": ["go-to-market", "gtm", "estratégia", "pricing", "roadmap"],
        "documentacao": ["documentação", "manual", "runbook", "spec", "guia"],
        "infra": ["infra", "kubernetes", "deploy", "observability", "sre"],
        "dev": ["python", "código", "bug", "teste", "refactor"],
    }

    def route(self, objective: str) -> dict[str, str]:
        text = objective.lower()
        for domain, keywords in self.DOMAINS.items():
            if any(k in text for k in keywords):
                return {"domain": domain, "template": f"Plano {domain}: objetivo='{objective}'"}
        return {"domain": "dev", "template": f"Plano dev: objetivo='{objective}'"}

    def expand_plan(self, objective: str) -> dict[str, Any]:
        routed = self.route(objective)
        domain = routed["domain"]
        playbooks = {
            "dados": ["inventariar fontes", "definir qualidade dos dados", "validar ETL"],
            "estrategia": ["diagnóstico de mercado", "hipóteses de crescimento", "plano de execução trimestral"],
            "documentacao": ["auditar lacunas", "escrever runbook", "validar com usuário final"],
            "infra": ["mapear gargalos", "definir SLO/SLI", "plano de rollout seguro"],
            "dev": ["reproduzir problema", "escrever testes", "aplicar patch mínimo"],
        }
        return {"domain": domain, "template": routed["template"], "playbook": playbooks.get(domain, playbooks["dev"])}
