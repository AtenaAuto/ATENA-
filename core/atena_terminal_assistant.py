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
            ("/self-test [quick]", "Executa validações automáticas da ATENA e gera relatório"),
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
        print("\nComandos: /task, /self-test, /plan, /review, /commit, /run, /context, /model, /clear, /exit\n")


def run_self_test(mode: str = "full") -> tuple[str, str]:
    checks = [
        ("doctor", ["./atena", "doctor"]),
        ("modules-smoke", ["./atena", "modules-smoke"]),
        ("go-no-go", ["./atena", "go-no-go"]),
    ]
    if mode == "quick":
        checks = checks[:2]

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
                timeout=180 if name == "go-no-go" else 120,
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
                mode = "quick" if "quick" in user_input.lower() else "full"
                with atena_thinking("Executando auto-validação da ATENA..."):
                    status, report_path = run_self_test(mode=mode)
                color = "green" if status == "ok" else "red"
                CONSOLE.print(f"[bold {color}]Self-test: {status.upper()}[/bold {color}]")
                CONSOLE.print(f"[dim]Relatório: {report_path}[/dim]")
                continue

            if user_input.startswith("/run "):
                cmd = user_input[5:].strip()
                CONSOLE.print(f"[dim]Executando: {cmd}[/dim]")
                os.system(cmd)
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
