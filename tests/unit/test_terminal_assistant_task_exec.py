from __future__ import annotations

import json
from pathlib import Path

import core.atena_terminal_assistant as assistant
from core.atena_terminal_assistant import sanitize_task_exec_commands


def test_sanitize_task_exec_commands_blocks_interactive_atena_commands() -> None:
    commands = [
        "./atena assistant",
        "./atena doctor",
        "./atena modules-smoke",
        "./atena orchestrator-mission",
    ]

    out = sanitize_task_exec_commands(commands)

    assert "./atena assistant" not in out
    assert "./atena doctor" in out
    assert "./atena modules-smoke" in out
    assert "./atena orchestrator-mission" in out


def test_sanitize_task_exec_commands_keeps_non_atena_safe_commands() -> None:
    commands = ["python3 -m py_compile core/main.py", "ls", "echo ok"]
    out = sanitize_task_exec_commands(commands)
    assert out == commands


def test_sanitize_task_exec_commands_blocks_bare_python_repl() -> None:
    commands = ["python", "python3", "python3 -m py_compile core/main.py"]
    out = sanitize_task_exec_commands(commands)
    assert "python" not in out
    assert "python3" not in out
    assert "python3 -m py_compile core/main.py" in out


def test_run_task_exec_builds_nodes_when_extractor_returns_empty(monkeypatch, tmp_path) -> None:
    class FakeRouter:
        def generate(self, prompt: str, context: str = "") -> str:  # noqa: ARG002
            return "./atena doctor\n./atena modules-smoke"

    monkeypatch.setattr(assistant, "ROOT", tmp_path)
    monkeypatch.setattr(assistant, "extract_dag_commands", lambda _text: [])
    monkeypatch.setattr(assistant, "append_learning_memory", lambda _payload: None)
    monkeypatch.setattr(assistant, "run_safe_command", lambda command, **kwargs: (0, f"ok:{command}", ""))  # noqa: ARG005

    status, report_path = assistant.run_task_exec(FakeRouter(), "objective")
    report = json.loads(Path(report_path).read_text(encoding="utf-8"))

    assert status == "ok"
    assert len(report["dag_nodes"]) == 2
    assert report["results"][0]["command"] == "./atena doctor"
