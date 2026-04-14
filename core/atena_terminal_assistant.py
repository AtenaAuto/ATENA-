#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ATENA Ω - Terminal Assistant (Claude Code Style)
Versão aprimorada com interface moderna e comandos intuitivos.
"""

import shlex
import subprocess
import threading
import time
import sys
import os
import logging
import json
import re
import socket
import webbrowser
from dataclasses import dataclass, field
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.atena_llm_router import AtenaLLMRouter

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.markdown import Markdown
    from rich.live import Live
    from rich.spinner import Spinner
    from rich.text import Text
    from rich.table import Table
    from rich.box import ROUNDED
    HAS_RICH = True
except Exception:
    HAS_RICH = False

# Configurações Globais
DASHBOARD_PORT = int(os.getenv("ATENA_DASHBOARD_PORT", "8765"))
ENABLE_DASHBOARD = os.getenv("ATENA_DASHBOARD_ENABLED", "0") == "1"
class PlainConsole:
    """Fallback simples para ambientes sem rich."""

    @staticmethod
    def print(*args, end: str = "\n", **kwargs) -> None:  # noqa: ANN003
        # ignora kwargs de estilo do rich
        text = " ".join(str(a) for a in args)
        print(text, end=end)


CONSOLE = Console() if HAS_RICH else PlainConsole()


def console_print(message: str) -> None:
    if HAS_RICH:
        CONSOLE.print(message)
    else:
        print(message)

@dataclass
class EvolutionState:
    cycles: int = 0
    running: bool = True
    last_started_at: Optional[str] = None
    last_finished_at: Optional[str] = None
    last_success: Optional[bool] = None
    last_error: Optional[str] = None
    lock: threading.Lock = field(default_factory=threading.Lock)
    wake_event: threading.Event = field(default_factory=threading.Event)

def git_branch() -> str:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=str(ROOT),
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        return out or "main"
    except Exception:
        return "local"

def get_prompt_label(model: str) -> Any:
    branch = git_branch()
    cwd = Path.cwd().name
    if HAS_RICH:
        prompt = Text()
        prompt.append(f" {branch} ", style="bold white on blue")
        prompt.append(f" {cwd} ", style="bold white on black")
        prompt.append(f" {model} ", style="bold black on cyan")
        prompt.append("\n ❯ ", style="bold magenta")
        return prompt
    return f"[{branch}][{cwd}][{model}] ❯ "

def render_banner():
    if HAS_RICH:
        CONSOLE.print("\n")
        CONSOLE.print(Panel(
            Text.assemble(
                ("🔱 ATENA Ω ", "bold cyan"),
                ("Assistant ", "bold white"),
                ("\n\n", ""),
                ("Inspirado no Claude Code. Digite ", "dim"),
                ("/help", "bold green"),
                (" para começar.", "dim")
            ),
            border_style="cyan",
            box=ROUNDED,
            padding=(1, 2)
        ))
    else:
        print("\n🔱 ATENA Ω Assistant - Digite /help para comandos.\n")

def print_help():
    if HAS_RICH:
        table = Table(show_header=True, header_style="bold magenta", box=ROUNDED)
        table.add_column("Comando", style="cyan")
        table.add_column("Descrição", style="white")
        
        commands = [
            ("/task <msg>", "Executa uma tarefa ou responde uma pergunta"),
            ("/task-exec <objetivo>", "Planeja e executa comandos seguros com relatório"),
            ("/self-test [quick]", "Executa validações automáticas da ATENA e gera relatório"),
            ("/release-governor", "Executa gates security/release/perf e decide GO/NO-GO"),
            ("/saas-bootstrap <nome>", "Gera stack SaaS web/api/cli + artefatos"),
            ("/telemetry-insights", "Resumo de falhas/sucessos por missão"),
            ("/orchestrate <objetivo>", "Executa orquestração multiagente por papéis"),
            ("/memory-suggest <objetivo>", "Sugere ação com base em memória histórica"),
            ("/benchmark", "Roda benchmark contínuo e atualiza leaderboard"),
            ("/device-control <pedido> [--confirm]", "Controla dispositivo local com permissões seguras"),
            ("/policy", "Mostra política de segurança para execução"),
            ("/plan <objetivo>", "Gera um plano de execução detalhado"),
            ("/review", "Revisa as mudanças atuais no código (git diff)"),
            ("/commit <msg>", "Realiza o commit das alterações atuais"),
            ("/run <cmd>", "Executa um comando no terminal"),
            ("/context", "Mostra o contexto atual da sessão"),
            ("/model", "Gerencia o modelo de IA utilizado"),
            ("/clear", "Limpa o terminal"),
            ("/exit", "Encerra o assistente")
        ]
        
        for cmd, desc in commands:
            table.add_row(cmd, desc)
        
        CONSOLE.print(Panel(table, title="[bold cyan]Comandos Disponíveis[/bold cyan]", border_style="cyan"))
    else:
        print("\nComandos: /task, /task-exec, /self-test, /release-governor, /saas-bootstrap, /telemetry-insights, /orchestrate, /memory-suggest, /benchmark, /device-control, /policy, /plan, /review, /commit, /run, /context, /model, /clear, /exit\n")


def run_self_test(mode: str = "full") -> tuple[str, str]:
    presets = {
        "quick": [
            ("doctor", ["./atena", "doctor"]),
            ("modules-smoke", ["./atena", "modules-smoke"]),
        ],
        "full": [
            ("doctor", ["./atena", "doctor"]),
            ("modules-smoke", ["./atena", "modules-smoke"]),
            ("go-no-go", ["./atena", "go-no-go"]),
        ],
        "security": [("guardian", ["./atena", "guardian"])],
        "release": [("production-ready", ["./atena", "production-ready"])],
        "perf": [
            ("modules-smoke", ["./atena", "modules-smoke"]),
            ("telemetry-report", ["./atena", "telemetry-report"]),
        ],
    }
    checks = presets.get(mode, presets["full"])

    report_dir = ROOT / "atena_evolution" / "assistant_self_tests"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"assistant_self_test_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"

    results: list[dict[str, object]] = []
    for name, cmd in checks:
        started = datetime.now(timezone.utc).isoformat()
        try:
            proc = subprocess.run(
                cmd,
                cwd=str(ROOT),
                capture_output=True,
                text=True,
                timeout=180 if name in {"go-no-go", "production-ready"} else 120,
            )
            rc = proc.returncode
            stdout = (proc.stdout or "")[-4000:]
            stderr = (proc.stderr or "")[-2000:]
        except subprocess.TimeoutExpired as exc:
            rc = 124
            stdout = (exc.stdout or "")[-4000:] if exc.stdout else ""
            stderr = f"timeout: {exc}"
        results.append(
            {
                "name": name,
                "command": " ".join(cmd),
                "started_at": started,
                "returncode": rc,
                "ok": rc == 0,
                "stdout_tail": stdout,
                "stderr_tail": stderr,
            }
        )

    status = "ok" if all(item["ok"] for item in results) else "failed"
    payload = {
        "status": status,
        "mode": mode,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "results": results,
    }
    report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    append_learning_memory({"event": "self_test", "mode": mode, "status": status, "report_path": str(report_path)})
    return status, str(report_path)


ALLOWED_PREFIXES = (
    "./atena",
    "python",
    "python3",
    "pytest",
    "uv ",
    "pip ",
    "ls",
    "cat",
    "echo",
    "pwd",
    "whoami",
    "date",
    "uname",
    "git status",
    "git diff",
)

DENY_PATTERNS = (
    r"(^|\s)rm\s+-rf\s+/",
    r"(^|\s)sudo(\s|$)",
    r"(^|\s)shutdown(\s|$)",
    r"(^|\s)reboot(\s|$)",
    r"mkfs\.",
    r"dd\s+if=",
    r"curl\s+.*\|\s*sh",
    r"wget\s+.*\|\s*sh",
    r"git\s+push",
)

READ_ONLY_PREFIXES = ("ls", "cat", "echo", "pwd", "whoami", "date", "uname", "git status", "git diff")
SLO_TARGETS = {
    "max_fail_rate": 0.20,
    "min_success_rate": 0.80,
}
APPROVAL_TIERS = {
    "tier0": {"desc": "read-only", "allowed": READ_ONLY_PREFIXES},
    "tier1": {"desc": "build-and-test", "allowed": ("./atena", "python", "python3", "pytest", "uv ", "pip ")},
    "tier2": {"desc": "mutable", "allowed": ALLOWED_PREFIXES},
}


def append_learning_memory(entry: dict[str, object]) -> None:
    memory_path = ROOT / "atena_evolution" / "assistant_learning_memory.jsonl"
    memory_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"timestamp": datetime.now(timezone.utc).isoformat(), **entry}
    with memory_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def validate_command_policy(command: str, context: str = "interactive", tier: str = "tier1") -> tuple[bool, str]:
    cmd = command.strip()
    if not cmd:
        return False, "comando vazio"
    for pattern in DENY_PATTERNS:
        if re.search(pattern, cmd):
            return False, f"bloqueado por política: {pattern}"
    tier_cfg = APPROVAL_TIERS.get(tier, APPROVAL_TIERS["tier1"])
    allowed_prefixes = tuple(tier_cfg["allowed"])
    if not cmd.startswith(allowed_prefixes):
        return False, "comando fora da allowlist"
    current_branch = git_branch()
    if current_branch == "main" and context in {"run", "task-exec"} and not cmd.startswith(READ_ONLY_PREFIXES):
        return False, "em branch main apenas comandos read-only são permitidos neste contexto"
    return True, "ok"


def run_safe_command(command: str, timeout: int = 120, context: str = "interactive", tier: str = "tier1") -> tuple[int, str, str]:
    allowed, reason = validate_command_policy(command, context=context, tier=tier)
    if not allowed:
        return 126, "", reason
    proc = subprocess.run(
        command,
        cwd=str(ROOT),
        shell=True,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return proc.returncode, proc.stdout or "", proc.stderr or ""


def extract_commands_from_plan(plan_text: str) -> list[str]:
    commands: list[str] = []
    for line in plan_text.splitlines():
        candidate = line.strip().strip("`").lstrip("-*0123456789. ").strip()
        if candidate.startswith(ALLOWED_PREFIXES):
            commands.append(candidate)
    unique = []
    for command in commands:
        if command not in unique:
            unique.append(command)
    return unique[:5]


def extract_dag_commands(plan_text: str) -> list[dict[str, object]]:
    commands = extract_commands_from_plan(plan_text)
    nodes = []
    for idx, cmd in enumerate(commands):
        deps = [] if idx == 0 else [idx - 1]
        nodes.append({"id": idx, "command": cmd, "deps": deps})
    return nodes


def execute_command_dag(nodes: list[dict[str, object]], context: str, tier: str = "tier1") -> list[dict[str, object]]:
    completed: set[int] = set()
    results: list[dict[str, object]] = []
    for node in nodes:
        deps = set(node["deps"])
        if not deps.issubset(completed):
            continue
        command = str(node["command"])
        rc, out, err = run_safe_command(command, timeout=180, context=context, tier=tier)
        results.append(
            {
                "id": node["id"],
                "deps": list(deps),
                "command": command,
                "returncode": rc,
                "ok": rc == 0,
                "stdout_tail": out[-2500:],
                "stderr_tail": err[-1200:],
            }
        )
        if rc == 0:
            completed.add(int(node["id"]))
        else:
            break
    return results


def rollback_from_command(command: str) -> str:
    match = re.search(r"--name\s+([a-zA-Z0-9_-]+)", command)
    if "code-build" in command and match:
        target = ROOT / "atena_evolution" / "generated_apps" / match.group(1)
        if target.exists():
            for path in sorted(target.rglob("*"), reverse=True):
                if path.is_file():
                    path.unlink(missing_ok=True)
                elif path.is_dir():
                    path.rmdir()
            target.rmdir()
            return f"rollback aplicado: removido {target}"
    return "rollback não necessário"


def run_task_exec(router: AtenaLLMRouter, objective: str) -> tuple[str, str]:
    planner_prompt = (
        "Retorne no máximo 5 comandos shell seguros para executar o objetivo. "
        "Use somente: ./atena, python3, pytest, ls, cat, git status, git diff, echo. "
        "Responda com 1 comando por linha.\n\n"
        f"Objetivo: {objective}"
    )
    plan_text = router.generate(planner_prompt, context="Atena task executor")
    commands = extract_commands_from_plan(plan_text) or ["./atena doctor", "./atena modules-smoke"]
    dag_nodes = extract_dag_commands("\n".join(commands))
    results = execute_command_dag(dag_nodes, context="task-exec", tier="tier1")
    rollback_logs: list[str] = []
    for item in results:
        if not item["ok"]:
            rollback_logs.append(rollback_from_command(str(item["command"])))
            break
    status = "ok" if all(item["ok"] for item in results) else "failed"
    report_dir = ROOT / "atena_evolution" / "task_exec_reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"task_exec_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
    report_path.write_text(
        json.dumps(
            {
                "status": status,
                "objective": objective,
                "plan_text": plan_text,
                "commands": commands,
                "dag_nodes": dag_nodes,
                "results": results,
                "rollback_logs": rollback_logs,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    append_learning_memory(
        {
            "event": "task_exec",
            "status": status,
            "objective": objective,
            "commands": commands,
            "report_path": str(report_path),
        }
    )
    return status, str(report_path)


def run_saas_bootstrap(project_name: str) -> tuple[str, str]:
    safe_name = "".join(ch for ch in project_name if ch.isalnum() or ch in ("-", "_")).strip("-_") or "atena_saas"
    commands = [
        f"./atena code-build --type site --template dashboard --name {safe_name}_web --validate",
        f"./atena code-build --type api --name {safe_name}_api --validate",
        f"./atena code-build --type cli --name {safe_name}_cli --validate",
    ]
    results = []
    for command in commands:
        rc, out, err = run_safe_command(command, timeout=240, context="saas-bootstrap")
        results.append({"command": command, "returncode": rc, "ok": rc == 0, "stdout_tail": out[-1800:], "stderr_tail": err[-800:]})

    bundle_dir = ROOT / "atena_evolution" / "generated_apps" / f"{safe_name}_bundle"
    bundle_dir.mkdir(parents=True, exist_ok=True)
    (bundle_dir / "docker-compose.yml").write_text(
        f"""services:\n  {safe_name}_api:\n    image: python:3.10-slim\n    working_dir: /app\n    command: sh -c \"pip install fastapi uvicorn && uvicorn main:app --host 0.0.0.0 --port 8000\"\n    volumes:\n      - ../{safe_name}_api:/app\n    ports:\n      - \"8000:8000\"\n""",
        encoding="utf-8",
    )
    (bundle_dir / "ci_stub.yml").write_text(
        "name: atena-saas-ci\non: [push]\njobs:\n  smoke:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/checkout@v4\n      - run: ./atena doctor\n      - run: ./atena modules-smoke\n",
        encoding="utf-8",
    )
    (bundle_dir / ".env.example").write_text(
        "APP_ENV=production\nJWT_SECRET=change_me\nDATABASE_URL=postgresql://user:pass@localhost:5432/app\n",
        encoding="utf-8",
    )
    (bundle_dir / "migration.sql").write_text(
        "CREATE TABLE IF NOT EXISTS users (\n  id SERIAL PRIMARY KEY,\n  email TEXT UNIQUE NOT NULL,\n  password_hash TEXT NOT NULL,\n  created_at TIMESTAMP DEFAULT NOW()\n);\n",
        encoding="utf-8",
    )
    (bundle_dir / "smoke_test.py").write_text(
        "def test_smoke():\n    assert True\n",
        encoding="utf-8",
    )
    (bundle_dir / "auth_stub.py").write_text(
        "def issue_token(user_id: str) -> str:\n    return f'token-{user_id}'\n",
        encoding="utf-8",
    )
    (bundle_dir / "healthcheck.sh").write_text(
        "#!/usr/bin/env bash\nset -euo pipefail\ncurl -sf http://localhost:8000/health\n",
        encoding="utf-8",
    )
    status = "ok" if all(item["ok"] for item in results) else "failed"
    report_path = bundle_dir / "bootstrap_report.json"
    report_path.write_text(json.dumps({"status": status, "project": safe_name, "results": results}, ensure_ascii=False, indent=2), encoding="utf-8")
    append_learning_memory({"event": "saas_bootstrap", "status": status, "project": safe_name, "report_path": str(report_path)})
    return status, str(report_path)


def telemetry_insights() -> str:
    telemetry_file = ROOT / "atena_evolution" / "telemetry_events.jsonl"
    if not telemetry_file.exists():
        return "Sem telemetria ainda. Rode missões para gerar eventos."
    total = 0
    fail = 0
    missions: dict[str, dict[str, int]] = {}
    for line in telemetry_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        total += 1
        mission = str(item.get("mission", "unknown"))
        status = str(item.get("status", "unknown"))
        missions.setdefault(mission, {"ok": 0, "fail": 0})
        if status == "ok":
            missions[mission]["ok"] += 1
        else:
            missions[mission]["fail"] += 1
            fail += 1
    top = sorted(missions.items(), key=lambda x: x[1]["fail"], reverse=True)[:3]
    fail_rate = (fail / total) if total else 0.0
    success_rate = 1.0 - fail_rate
    slo_ok = fail_rate <= SLO_TARGETS["max_fail_rate"] and success_rate >= SLO_TARGETS["min_success_rate"]
    lines = [
        f"Eventos totais: {total}",
        f"Falhas totais: {fail}",
        f"Fail rate: {fail_rate:.2%}",
        f"Success rate: {success_rate:.2%}",
        f"SLO status: {'OK' if slo_ok else 'ALERTA'}",
        "Top missões por falha:",
    ]
    lines.extend([f"- {name}: fail={stats['fail']} ok={stats['ok']}" for name, stats in top])
    lines.append("SLO por missão:")
    for name, stats in sorted(missions.items()):
        count = stats["ok"] + stats["fail"]
        mission_fail_rate = (stats["fail"] / count) if count else 0.0
        mission_status = "ALERTA" if mission_fail_rate > SLO_TARGETS["max_fail_rate"] else "OK"
        lines.append(f"- {name}: fail_rate={mission_fail_rate:.2%} status={mission_status}")
    append_learning_memory({"event": "telemetry_insights", "status": "ok" if slo_ok else "alert", "fail_rate": fail_rate, "success_rate": success_rate})
    return "\n".join(lines)


def run_release_governor() -> tuple[str, str]:
    sequence = ["security", "release", "perf"]
    details = []
    weights = {"security": 0.5, "release": 0.3, "perf": 0.2}
    score = 0.0
    for mode in sequence:
        status, report_path = run_self_test(mode=mode)
        details.append({"mode": mode, "status": status, "report_path": report_path})
        score += weights.get(mode, 0.0) * (1.0 if status == "ok" else 0.0)
    final_status = "go" if score >= 0.8 else "no-go"
    remediation = "Executar ./atena fix e repetir /self-test security" if final_status == "no-go" else "Sistema aprovado para evolução."
    governor_dir = ROOT / "atena_evolution" / "release_governor"
    governor_dir.mkdir(parents=True, exist_ok=True)
    out_path = governor_dir / f"release_governor_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
    out_path.write_text(
        json.dumps({"status": final_status, "score": round(score, 3), "checks": details, "remediation": remediation, "generated_at": datetime.now(timezone.utc).isoformat()}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    append_learning_memory({"event": "release_governor", "status": final_status, "report_path": str(out_path)})
    return final_status, str(out_path)


def suggest_from_memory(objective: str) -> str:
    memory_path = ROOT / "atena_evolution" / "assistant_learning_memory.jsonl"
    if not memory_path.exists():
        return "Sem memória histórica ainda."
    query_tokens = set(re.findall(r"\w+", objective.lower()))
    scored: list[tuple[int, dict[str, object]]] = []
    for line in memory_path.read_text(encoding="utf-8").splitlines():
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        text = json.dumps(item, ensure_ascii=False).lower()
        score = sum(1 for token in query_tokens if token in text)
        if score:
            scored.append((score, item))
    scored.sort(key=lambda x: x[0], reverse=True)
    best = [entry for _, entry in scored[:3]]
    if not best:
        return "Nenhum caso similar encontrado."
    lines = ["Top casos similares:"]
    for item in best:
        lines.append(f"- event={item.get('event')} status={item.get('status')} report={item.get('report_path', '-')}")
    return "\n".join(lines)


def run_multi_agent_orchestrator(router: AtenaLLMRouter, objective: str) -> tuple[str, str]:
    roles = ["planner", "builder", "reviewer", "security", "release"]
    outputs = {}
    for role in roles:
        prompt = f"Você é o agente {role}. Objetivo: {objective}. Entregue resumo objetivo e próximo passo."
        outputs[role] = router.generate(prompt, context=f"multi-agent:{role}")
    orchestration_dir = ROOT / "atena_evolution" / "multi_agent_runs"
    orchestration_dir.mkdir(parents=True, exist_ok=True)
    out_path = orchestration_dir / f"orchestrate_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
    out_path.write_text(json.dumps({"objective": objective, "outputs": outputs}, ensure_ascii=False, indent=2), encoding="utf-8")
    append_learning_memory({"event": "orchestrate", "status": "ok", "objective": objective, "report_path": str(out_path)})
    return "ok", str(out_path)


def run_benchmark_suite() -> tuple[str, str]:
    suites = ["quick", "security", "perf"]
    points = {"quick": 20, "security": 40, "perf": 40}
    total = 0
    details = []
    for suite in suites:
        status, report_path = run_self_test(mode=suite)
        earned = points[suite] if status == "ok" else 0
        total += earned
        details.append({"suite": suite, "status": status, "points": earned, "report_path": report_path})
    leaderboard_dir = ROOT / "atena_evolution" / "benchmarks"
    leaderboard_dir.mkdir(parents=True, exist_ok=True)
    out_path = leaderboard_dir / "leaderboard.jsonl"
    entry = {"timestamp": datetime.now(timezone.utc).isoformat(), "score": total, "details": details}
    with out_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    append_learning_memory({"event": "benchmark", "status": "ok", "score": total, "report_path": str(out_path)})
    return ("ok" if total >= 80 else "alert"), str(out_path)


def run_device_control(request: str, confirmed: bool) -> tuple[str, str]:
    report_dir = ROOT / "atena_evolution" / "device_control"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"device_control_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')}.json"

    if not confirmed:
        payload = {
            "status": "blocked",
            "reason": "confirmation_required",
            "request": request,
            "allowed_actions": [
                "abrir URL (http/https)",
                "diagnóstico rápido do sistema",
                "status básico do sistema",
            ],
        }
        report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return "blocked", str(report_path)

    req = request.strip().lower()
    action = "unknown"
    result: dict[str, object] = {"request": request}

    url_match = re.search(r"(https?://[^\s]+)", request, flags=re.IGNORECASE)
    if ("abrir" in req or "open" in req) and url_match:
        action = "open_url"
        url = url_match.group(1)
        ok = webbrowser.open(url)
        result.update({"action": action, "url": url, "ok": bool(ok)})
    elif "diagnost" in req or "teste" in req:
        action = "self_test_quick"
        status, path = run_self_test(mode="quick")
        result.update({"action": action, "status": status, "report": path})
    elif "status" in req or "sistema" in req:
        action = "system_status"
        rc, out, err = run_safe_command("uname -a", context="device-control", tier="tier0")
        result.update({"action": action, "returncode": rc, "stdout": out[-800:], "stderr": err[-400:]})
    else:
        result.update({"action": action, "status": "unsupported_request"})

    final_status = "ok" if result.get("action") != "unknown" and result.get("status") != "unsupported_request" else "failed"
    payload = {"status": final_status, **result}
    report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    append_learning_memory({"event": "device_control", "status": final_status, "action": action, "report_path": str(report_path)})
    return final_status, str(report_path)

@contextmanager
def atena_thinking(message: str = "Pensando..."):
    if HAS_RICH:
        with Live(Spinner("dots", text=Text(message, style="cyan"), style="magenta"), refresh_per_second=10, transient=True):
            yield
    else:
        print(f"◐ {message}", end="\r")
        yield
        print(" " * 50, end="\r")

def main():
    render_banner()
    router = AtenaLLMRouter()
    
    # Silenciar logs barulhentos
    for logger_name in ["AtenaUltraBrain", "httpx", "huggingface_hub", "transformers"]:
        logging.getLogger(logger_name).setLevel(logging.ERROR)

    while True:
        try:
            prompt = get_prompt_label(router.current())
            if HAS_RICH:
                CONSOLE.print(prompt, end="")
                user_input = input().strip()
            else:
                user_input = input(prompt).strip()
            
            if not user_input:
                continue
            
            if user_input in ["/exit", "exit", "quit", "/quit", "/q", ":q", "/sair", "sair"]:
                console_print("[bold red]Encerrando ATENA... Até logo![/bold red]" if HAS_RICH else "Encerrando ATENA... Até logo!")
                break
            
            if user_input == "/help":
                print_help()
                continue
            
            if user_input == "/clear":
                os.system("clear")
                continue
            
            if user_input == "/context":
                if HAS_RICH:
                    CONSOLE.print(Panel(
                        f"CWD: [cyan]{ROOT}[/cyan]\nBranch: [magenta]{git_branch()}[/magenta]\nModelo: [green]{router.current()}[/green]",
                        title="Contexto Atual", border_style="blue"
                    ))
                continue

            if user_input.startswith("/self-test"):
                parts = user_input.split(maxsplit=1)
                mode = parts[1].strip().lower() if len(parts) > 1 else "full"
                with atena_thinking("Executando auto-validação da ATENA..."):
                    status, report_path = run_self_test(mode=mode)
                color = "green" if status == "ok" else "red"
                CONSOLE.print(f"[bold {color}]Self-test: {status.upper()}[/bold {color}]")
                CONSOLE.print(f"[dim]Relatório: {report_path}[/dim]")
                continue

            if user_input == "/release-governor":
                with atena_thinking("Executando Release Governor..."):
                    status, report_path = run_release_governor()
                color = "green" if status == "go" else "red"
                CONSOLE.print(f"[bold {color}]Release Governor: {status.upper()}[/bold {color}]")
                CONSOLE.print(f"[dim]Relatório: {report_path}[/dim]")
                continue

            if user_input == "/policy":
                CONSOLE.print("[bold cyan]Policy Engine[/bold cyan]")
                CONSOLE.print(f"Allowlist: {', '.join(ALLOWED_PREFIXES)}")
                CONSOLE.print(f"Bloqueios: {', '.join(DENY_PATTERNS)}")
                CONSOLE.print("Tiers: " + ", ".join(f"{name}={cfg['desc']}" for name, cfg in APPROVAL_TIERS.items()))
                continue

            if user_input.startswith("/orchestrate "):
                objective = user_input[len("/orchestrate "):].strip()
                with atena_thinking("Executando orquestração multiagente..."):
                    status, report_path = run_multi_agent_orchestrator(router, objective)
                color = "green" if status == "ok" else "red"
                CONSOLE.print(f"[bold {color}]Orchestrate: {status.upper()}[/bold {color}]")
                CONSOLE.print(f"[dim]Relatório: {report_path}[/dim]")
                continue

            if user_input.startswith("/memory-suggest "):
                objective = user_input[len("/memory-suggest "):].strip()
                CONSOLE.print(Panel(suggest_from_memory(objective), title="[bold cyan]Memory Suggest[/bold cyan]", border_style="cyan"))
                continue

            if user_input == "/benchmark":
                with atena_thinking("Executando benchmark contínuo..."):
                    status, report_path = run_benchmark_suite()
                color = "green" if status == "ok" else "yellow"
                CONSOLE.print(f"[bold {color}]Benchmark: {status.upper()}[/bold {color}]")
                CONSOLE.print(f"[dim]Leaderboard: {report_path}[/dim]")
                continue

            if user_input.startswith("/device-control "):
                raw = user_input[len("/device-control "):].strip()
                confirmed = raw.endswith("--confirm")
                request = raw[:-9].strip() if confirmed else raw
                with atena_thinking("Executando device control..."):
                    status, report_path = run_device_control(request=request, confirmed=confirmed)
                color = "green" if status == "ok" else ("yellow" if status == "blocked" else "red")
                CONSOLE.print(f"[bold {color}]Device control: {status.upper()}[/bold {color}]")
                CONSOLE.print(f"[dim]Relatório: {report_path}[/dim]")
                if status == "blocked":
                    CONSOLE.print("[yellow]Use --confirm para executar ações de controle de dispositivo.[/yellow]")
                continue

            if user_input.startswith("/run "):
                cmd = user_input[5:].strip()
                CONSOLE.print(f"[dim]Executando: {cmd}[/dim]")
                rc, out, err = run_safe_command(cmd, context="run")
                if out:
                    CONSOLE.print(out.rstrip())
                if err:
                    CONSOLE.print(f"[yellow]{err.rstrip()}[/yellow]")
                CONSOLE.print(f"[dim]returncode={rc}[/dim]")
                continue

            if user_input.startswith("/task-exec "):
                objective = user_input[len("/task-exec "):].strip()
                with atena_thinking("Planejando e executando tarefa..."):
                    status, report_path = run_task_exec(router, objective)
                color = "green" if status == "ok" else "red"
                CONSOLE.print(f"[bold {color}]Task exec: {status.upper()}[/bold {color}]")
                CONSOLE.print(f"[dim]Relatório: {report_path}[/dim]")
                continue

            if user_input.startswith("/saas-bootstrap "):
                project_name = user_input[len("/saas-bootstrap "):].strip()
                with atena_thinking("Gerando stack SaaS completa..."):
                    status, report_path = run_saas_bootstrap(project_name)
                color = "green" if status == "ok" else "red"
                CONSOLE.print(f"[bold {color}]SaaS bootstrap: {status.upper()}[/bold {color}]")
                CONSOLE.print(f"[dim]Relatório: {report_path}[/dim]")
                continue

            if user_input == "/telemetry-insights":
                CONSOLE.print(Panel(telemetry_insights(), title="[bold cyan]Telemetry Insights[/bold cyan]", border_style="cyan"))
                continue

            # Processamento de Tarefas (Task)
            if user_input.startswith("/task "):
                task_msg = user_input[6:].strip()
                with atena_thinking("Processando tarefa..."):
                    answer = router.generate(task_msg, context="Claude Code Style Assistant")
                
                if HAS_RICH:
                    CONSOLE.print(Panel(Markdown(answer), title="[bold cyan]ATENA[/bold cyan]", border_style="cyan"))
                else:
                    print(f"\nATENA:\n{answer}\n")
                continue

            # Comando padrão (se não começar com / assume-se /task)
            if not user_input.startswith("/"):
                with atena_thinking("Analisando..."):
                    answer = router.generate(user_input, context="Claude Code Style Assistant")
                if HAS_RICH:
                    CONSOLE.print(Panel(Markdown(answer), title="[bold cyan]ATENA[/bold cyan]", border_style="cyan"))
                else:
                    print(f"\nATENA:\n{answer}\n")
                continue

            console_print(
                f"[yellow]Comando desconhecido: {user_input}. Digite /help para ajuda.[/yellow]"
                if HAS_RICH
                else f"Comando desconhecido: {user_input}. Digite /help para ajuda."
            )

        except EOFError:
            if HAS_RICH:
                CONSOLE.print("\n[yellow]Entrada finalizada (EOF). Encerrando assistente.[/yellow]")
            else:
                print("\nEntrada finalizada (EOF). Encerrando assistente.")
            break
        except KeyboardInterrupt:
            console_print(
                "\n[yellow]Interrompido pelo usuário. Digite /exit para sair.[/yellow]"
                if HAS_RICH
                else "\nInterrompido pelo usuário. Digite /exit para sair."
            )
        except Exception as e:
            console_print(f"[bold red]Erro:[/bold red] {str(e)}" if HAS_RICH else f"Erro: {str(e)}")

if __name__ == "__main__":
    sys.exit(main())
