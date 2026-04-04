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
INVOKE_SCRIPT = ROOT / "protocols" / "atena_invoke.py"
DASHBOARD_SCRIPT = ROOT / "core" / "atena_local_dashboard.py"
DASHBOARD_PORT = int(os.getenv("ATENA_DASHBOARD_PORT", "8765"))
DASHBOARD_STATE_FILE = ROOT / "atena_evolution" / "assistant_dashboard_state.json"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.atena_llm_router import AtenaLLMRouter


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
    open_dashboard()
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
    finally:
        write_dashboard_state(state)


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
  /model                mostra backend/modelo atual
  /model list           mostra opções de LLM/provider
  /model set <spec>     troca backend (ex: local | openai:gpt-4.1-mini | compat:claude-3-5-sonnet)
  /task <instrução>     pede para ATENA pensar em uma tarefa (resposta textual)
  /feedback <0-1>       reforça aprendizado da última resposta (ex: /feedback 0.95)
  /run <cmd>            executa comando shell local (use com cuidado)
  /dashboard            abre/mostra dashboard local com chat da ATENA
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


@contextmanager
def suppress_noisy_runtime():
    """
    Silencia ruído de bibliotecas enquanto o spinner está ativo.
    Evita "poluição visual" no terminal durante processamento.
    """
    noisy = [
        "AtenaUltraBrain",
        "httpx",
        "huggingface_hub",
        "transformers",
    ]
    previous = {}
    for name in noisy:
        lg = logging.getLogger(name)
        previous[name] = lg.level
        lg.setLevel(logging.ERROR)
    with open(os.devnull, "w", encoding="utf-8") as null:
        with redirect_stdout(null), redirect_stderr(null):
            yield
    for name, level in previous.items():
        logging.getLogger(name).setLevel(level)


def _is_port_open(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.25)
        return sock.connect_ex((host, port)) == 0


def dashboard_url() -> str:
    return f"http://127.0.0.1:{DASHBOARD_PORT}"


def ensure_dashboard_running() -> None:
    if _is_port_open("127.0.0.1", DASHBOARD_PORT):
        return
    subprocess.Popen(
        ["python3", str(DASHBOARD_SCRIPT), "--port", str(DASHBOARD_PORT)],
        cwd=str(ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    for _ in range(20):
        if _is_port_open("127.0.0.1", DASHBOARD_PORT):
            return
        time.sleep(0.1)


def open_dashboard() -> None:
    ensure_dashboard_running()
    try:
        webbrowser.open(dashboard_url())
    except Exception:
        pass


def write_dashboard_state(state: EvolutionState) -> None:
    DASHBOARD_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with state.lock:
        payload = {
            "cycles": state.cycles,
            "last_started_at": state.last_started_at,
            "last_finished_at": state.last_finished_at,
            "last_success": state.last_success,
            "last_error": state.last_error,
        }
    DASHBOARD_STATE_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    print(
        """
🔱 ATENA-Like Assistant
    █████╗ ████████╗███████╗███╗   ██╗ █████╗
   ██╔══██╗╚══██╔══╝██╔════╝████╗  ██║██╔══██╗
   ███████║   ██║   █████╗  ██╔██╗ ██║███████║
   ██╔══██║   ██║   ██╔══╝  ██║╚██╗██║██╔══██║
   ██║  ██║   ██║   ███████╗██║ ╚████║██║  ██║
   ╚═╝  ╚═╝   ╚═╝   ╚══════╝╚═╝  ╚═══╝╚═╝  ╚═╝
"""
    )
    print("Evolução em segundo plano: ATIVA.")
    print("Digite /help para ver os comandos.")

    router = AtenaLLMRouter()
    # Mantém o terminal limpo no modo assistant.
    logging.getLogger("AtenaUltraBrain").setLevel(logging.ERROR)
    logging.getLogger("httpx").setLevel(logging.ERROR)
    logging.getLogger("huggingface_hub").setLevel(logging.ERROR)
    logging.getLogger("transformers").setLevel(logging.ERROR)
    local_ready = False
    last_prompt: Optional[str] = None
    last_response: Optional[str] = None

    def warmup_llm(show_spinner: bool = True):
        nonlocal local_ready
        if local_ready:
            return
        if router.cfg.provider == "local":
            spinner = AtenaSpinner("Inicializando cérebro local da ATENA-Like") if show_spinner else None
            if spinner:
                spinner.start()
            try:
                # força lazy init local
                with suppress_noisy_runtime():
                    router.generate("teste rápido", context="warmup")
            finally:
                if spinner:
                    spinner.stop("pronto")
            local_ready = True
    state = EvolutionState()
    write_dashboard_state(state)
    ensure_dashboard_running()
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
                open_dashboard()
                state.wake_event.set()
                print("✅ Ciclo de evolução solicitado em background.")
                continue
            if raw == "/dashboard":
                open_dashboard()
                print(f"✅ Dashboard local: {dashboard_url()}")
                continue
            if raw == "/model":
                print(f"Modelo atual: {router.current()}")
                continue
            if raw == "/model list":
                print("Opções de modelo/provider:")
                for opt in router.list_options():
                    print(f"- {opt}")
                continue
            if raw.startswith("/model set "):
                spec = raw[len("/model set ") :].strip()
                ok, msg = router.set_backend(spec)
                print(("✅ " if ok else "❌ ") + msg)
                local_ready = False
                continue
            if raw.startswith("/feedback "):
                score_txt = raw[len("/feedback ") :].strip()
                if not score_txt:
                    print("Informe uma nota entre 0 e 1. Ex: /feedback 0.9")
                    continue
                try:
                    score = float(score_txt)
                except ValueError:
                    print("Nota inválida. Use um número entre 0 e 1.")
                    continue
                if score < 0 or score > 1:
                    print("Nota fora do intervalo. Use entre 0 e 1.")
                    continue
                if not last_prompt or not last_response:
                    print("Não há resposta anterior para aprender ainda.")
                    continue
                router.learn_from_feedback(
                    prompt=last_prompt,
                    response=last_response,
                    success=score >= 0.6,
                    score=score,
                )
                print(f"🧠 Feedback aplicado (score={score:.2f}) na memória da ATENA-Like.")
                continue
            if raw.startswith("/task "):
                task = raw[len("/task ") :].strip()
                if not task:
                    print("Informe uma instrução após /task.")
                    continue
                spinner = AtenaSpinner("ATENA-Like pensando na tarefa")
                spinner.start()
                try:
                    if router.cfg.provider == "local":
                        warmup_llm(show_spinner=False)
                    with suppress_noisy_runtime():
                        answer = router.generate(task, context="Modo assistant no terminal")
                finally:
                    spinner.stop("resposta gerada")
                router.learn_from_feedback(
                    prompt=task,
                    response=answer,
                    success=True,
                    score=0.75,
                )
                last_prompt = task
                last_response = answer
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
                if router.cfg.provider == "local":
                    warmup_llm(show_spinner=False)
                with suppress_noisy_runtime():
                    answer = router.generate(raw, context="Conversa livre no terminal")
            finally:
                spinner.stop("resposta gerada")
            router.learn_from_feedback(
                prompt=raw,
                response=answer,
                success=True,
                score=0.7,
            )
            last_prompt = raw
            last_response = answer
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
