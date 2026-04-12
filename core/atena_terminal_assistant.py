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
from typing import Optional

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
CONSOLE = Console() if HAS_RICH else None

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

def get_prompt_label(model: str) -> Text:
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
            ("/saas-bootstrap <nome>", "Gera stack SaaS web/api/cli + artefatos"),
            ("/telemetry-insights", "Resumo de falhas/sucessos por missão"),
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
        print("\nComandos: /task, /task-exec, /self-test, /saas-bootstrap, /telemetry-insights, /policy, /plan, /review, /commit, /run, /context, /model, /clear, /exit\n")


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


def validate_command_policy(command: str) -> tuple[bool, str]:
    cmd = command.strip()
    if not cmd:
        return False, "comando vazio"
    for pattern in DENY_PATTERNS:
        if re.search(pattern, cmd):
            return False, f"bloqueado por política: {pattern}"
    if not cmd.startswith(ALLOWED_PREFIXES):
        return False, "comando fora da allowlist"
    return True, "ok"


def run_safe_command(command: str, timeout: int = 120) -> tuple[int, str, str]:
    allowed, reason = validate_command_policy(command)
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


def run_task_exec(router: AtenaLLMRouter, objective: str) -> tuple[str, str]:
    planner_prompt = (
        "Retorne no máximo 5 comandos shell seguros para executar o objetivo. "
        "Use somente: ./atena, python3, pytest, ls, cat, git status, git diff, echo. "
        "Responda com 1 comando por linha.\n\n"
        f"Objetivo: {objective}"
    )
    plan_text = router.generate(planner_prompt, context="Atena task executor")
    commands = extract_commands_from_plan(plan_text) or ["./atena doctor", "./atena modules-smoke"]
    results: list[dict[str, object]] = []
    for command in commands:
        rc, out, err = run_safe_command(command, timeout=180)
        results.append(
            {
                "command": command,
                "returncode": rc,
                "ok": rc == 0,
                "stdout_tail": out[-2500:],
                "stderr_tail": err[-1200:],
            }
        )
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
                "results": results,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
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
        rc, out, err = run_safe_command(command, timeout=240)
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
    status = "ok" if all(item["ok"] for item in results) else "failed"
    report_path = bundle_dir / "bootstrap_report.json"
    report_path.write_text(json.dumps({"status": status, "project": safe_name, "results": results}, ensure_ascii=False, indent=2), encoding="utf-8")
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
    lines = [f"Eventos totais: {total}", f"Falhas totais: {fail}", "Top missões por falha:"]
    lines.extend([f"- {name}: fail={stats['fail']} ok={stats['ok']}" for name, stats in top])
    return "\n".join(lines)

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
                CONSOLE.print("[bold red]Encerrando ATENA... Até logo![/bold red]")
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

            if user_input == "/policy":
                CONSOLE.print("[bold cyan]Policy Engine[/bold cyan]")
                CONSOLE.print(f"Allowlist: {', '.join(ALLOWED_PREFIXES)}")
                CONSOLE.print(f"Bloqueios: {', '.join(DENY_PATTERNS)}")
                continue

            if user_input.startswith("/run "):
                cmd = user_input[5:].strip()
                CONSOLE.print(f"[dim]Executando: {cmd}[/dim]")
                rc, out, err = run_safe_command(cmd)
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

            CONSOLE.print(f"[yellow]Comando desconhecido: {user_input}. Digite /help para ajuda.[/yellow]")

        except EOFError:
            if HAS_RICH:
                CONSOLE.print("\n[yellow]Entrada finalizada (EOF). Encerrando assistente.[/yellow]")
            else:
                print("\nEntrada finalizada (EOF). Encerrando assistente.")
            break
        except KeyboardInterrupt:
            CONSOLE.print("\n[yellow]Interrompido pelo usuário. Digite /exit para sair.[/yellow]")
        except Exception as e:
            CONSOLE.print(f"[bold red]Erro:[/bold red] {str(e)}")

if __name__ == "__main__":
    sys.exit(main())
