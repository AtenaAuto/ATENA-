#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Launcher bonito da ATENA-Like (estilo CLI moderno)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

COMMANDS = {
    "start": ROOT / "core" / "main.py",
    "invoke": ROOT / "protocols" / "atena_invoke.py",
    "dialog": ROOT / "protocols" / "atena_dialogue_session.py",
    "assistant": ROOT / "core" / "atena_terminal_assistant.py",
    "doctor": ROOT / "core" / "atena_doctor.py",
    "fix": ROOT / "core" / "atena_fix.py",
}

ALIASES = {
    "atena-like": "assistant",
    "like": "assistant",
}


def render_help() -> None:
    try:
        from rich.console import Console
        from rich.table import Table

        console = Console()
        console.print("\n[bold cyan]🔱 ATENA-Like CLI[/bold cyan]\n")
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Comando")
        table.add_column("Descrição")
        table.add_row("./atena", "Inicia o núcleo principal")
        table.add_row("./atena start", "Núcleo principal")
        table.add_row("./atena invoke", "Missão avançada de criação de script")
        table.add_row("./atena dialog", "Sessão de diálogo")
        table.add_row("./atena assistant", "Modo assistente com evolução em background")
        table.add_row("./atena doctor", "Diagnóstico rápido (estilo healthcheck)")
        table.add_row("./atena doctor --full", "Diagnóstico completo (runtime)")
        table.add_row("./atena fix", "Auto-correções básicas do ambiente")
        table.add_row("./atena atena-like", "Alias do modo assistant")
        table.add_row("./atena help", "Exibe esta ajuda")
        console.print(table)
        console.print("\n[dim]Dica: use /help dentro do modo assistant.[/dim]\n")
    except Exception:
        print("🔱 ATENA-Like CLI\n")
        print("Uso:")
        print("  ./atena                 # inicia o núcleo principal")
        print("  ./atena start           # núcleo principal")
        print("  ./atena invoke          # missão avançada")
        print("  ./atena dialog          # sessão de diálogo")
        print("  ./atena assistant       # assistente + evolução")
        print("  ./atena doctor          # diagnóstico rápido")
        print("  ./atena doctor --full   # diagnóstico completo")
        print("  ./atena fix             # auto-correções básicas")
        print("  ./atena atena-like      # alias do assistant")
        print("  ./atena help            # ajuda")


def normalize_command(arg: str | None) -> str:
    if not arg:
        return "start"
    arg = arg.strip().lower()
    if arg in ("-h", "--help", "help"):
        return "help"
    return ALIASES.get(arg, arg)


def main(argv: list[str]) -> int:
    command = normalize_command(argv[1] if len(argv) > 1 else None)
    if command == "help":
        render_help()
        return 0

    script = COMMANDS.get(command)
    if script is None:
        print(f"Comando inválido: {command}\n")
        render_help()
        return 2

    result = subprocess.run([sys.executable, str(script), *argv[2:]], cwd=str(ROOT))
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
