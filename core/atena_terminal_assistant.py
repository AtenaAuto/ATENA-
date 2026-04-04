#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ATENA Ω - Terminal Assistant

Modo interativo de terminal com:
1) conversa/tarefas em foreground;
2) evolução contínua em background.
"""

import shlex
import subprocess
import threading
import time
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent
INVOKE_SCRIPT = ROOT / "protocols" / "atena_invoke.py"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.atena_local_lm import AtenaUltraBrain


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


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_evolution_cycle(state: EvolutionState) -> None:
    with state.lock:
        state.cycles += 1
        state.last_started_at = utc_now_iso()
        state.last_error = None
    try:
        proc = subprocess.run(
            ["python3", str(INVOKE_SCRIPT)],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=180,
        )
        with state.lock:
            state.last_finished_at = utc_now_iso()
            state.last_success = proc.returncode == 0
            if proc.returncode != 0:
                state.last_error = (proc.stderr or proc.stdout or "erro desconhecido").strip()[:800]
    except Exception as exc:  # noqa: BLE001
        with state.lock:
            state.last_finished_at = utc_now_iso()
            state.last_success = False
            state.last_error = str(exc)


def evolution_worker(state: EvolutionState, interval_seconds: int) -> None:
    while state.running:
        woke = state.wake_event.wait(timeout=interval_seconds)
        state.wake_event.clear()
        if not state.running:
            return
        if woke:
            run_evolution_cycle(state)
        else:
            run_evolution_cycle(state)


def print_help() -> None:
    print(
        """
Comandos:
  /help                 mostra ajuda
  /status               mostra status da evolução em background
  /evolve               dispara um ciclo de evolução imediatamente
  /task <instrução>     pede para ATENA pensar em uma tarefa (resposta textual)
  /run <cmd>            executa comando shell local (use com cuidado)
  /exit                 encerra o modo assistant
"""
    )


class AtenaSpinner:
    """Spinner simples para indicar processamento da ATENA no terminal."""

    def __init__(self, message: str = "ATENA processando"):
        self.message = message
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._frames = ["◐", "◓", "◑", "◒"]

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        idx = 0
        while self._running:
            frame = self._frames[idx % len(self._frames)]
            print(f"\r{frame} {self.message}...", end="", flush=True)
            time.sleep(0.12)
            idx += 1

    def stop(self, done_message: str = "concluído"):
        self._running = False
        if self._thread:
            self._thread.join(timeout=1)
        print(f"\r✅ {self.message}: {done_message}." + " " * 12)


def main() -> int:
    print("🔱 ATENA-Like Assistant iniciada.")
    print("Evolução em segundo plano: ATIVA.")
    print("Digite /help para ver os comandos.")

    brain: Optional[AtenaUltraBrain] = None

    def get_brain() -> AtenaUltraBrain:
        nonlocal brain
        if brain is None:
            spinner = AtenaSpinner("Inicializando cérebro local da ATENA-Like")
            spinner.start()
            try:
                brain = AtenaUltraBrain()
            finally:
                spinner.stop("pronto")
        return brain
    state = EvolutionState()
    interval_seconds = 600
    worker = threading.Thread(target=evolution_worker, args=(state, interval_seconds), daemon=True)
    worker.start()

    try:
        while True:
            raw = input("\nATENA> ").strip()
            if not raw:
                continue
            if raw == "/exit":
                break
            if raw == "/help":
                print_help()
                continue
            if raw == "/status":
                with state.lock:
                    print(
                        f"cycles={state.cycles} | last_success={state.last_success} | "
                        f"last_started_at={state.last_started_at} | last_finished_at={state.last_finished_at}"
                    )
                    if state.last_error:
                        print(f"last_error={state.last_error}")
                continue
            if raw == "/evolve":
                state.wake_event.set()
                print("✅ Ciclo de evolução solicitado em background.")
                continue
            if raw.startswith("/task "):
                task = raw[len("/task ") :].strip()
                if not task:
                    print("Informe uma instrução após /task.")
                    continue
                spinner = AtenaSpinner("ATENA-Like pensando na tarefa")
                spinner.start()
                try:
                    answer = get_brain().think(task, context="Modo assistant no terminal")
                finally:
                    spinner.stop("resposta gerada")
                print("\n" + answer[:4000])
                continue
            if raw.startswith("/run "):
                cmd = raw[len("/run ") :].strip()
                if not cmd:
                    print("Informe um comando após /run.")
                    continue
                try:
                    completed = subprocess.run(
                        shlex.split(cmd),
                        cwd=str(ROOT),
                        capture_output=True,
                        text=True,
                        timeout=120,
                    )
                    print(completed.stdout[:3000])
                    if completed.returncode != 0:
                        print(completed.stderr[:1500])
                except Exception as exc:  # noqa: BLE001
                    print(f"Falha ao executar comando: {exc}")
                continue

            spinner = AtenaSpinner("ATENA-Like elaborando resposta")
            spinner.start()
            try:
                answer = get_brain().think(raw, context="Conversa livre no terminal")
            finally:
                spinner.stop("resposta gerada")
            print("\n" + answer[:4000])
    except (EOFError, KeyboardInterrupt):
        print("\nEncerrando ATENA Ω Assistant...")
    finally:
        state.running = False
        state.wake_event.set()
        worker.join(timeout=2)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
