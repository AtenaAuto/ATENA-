from __future__ import annotations

from modules.atena_codex import AtenaCodex


def test_check_python_modules_exposes_advanced_group() -> None:
    codex = AtenaCodex()
    checks = codex.check_python_modules()

    assert "essential" in checks
    assert "advanced" in checks
    assert "optional" in checks


def test_run_full_diagnostic_treats_soft_fail_as_warning(monkeypatch) -> None:
    codex = AtenaCodex()

    monkeypatch.setattr(codex, "environment_snapshot", lambda: {"host": "test"})
    monkeypatch.setattr(
        codex,
        "check_python_modules",
        lambda: {
            "essential": [{"name": "requests", "ok": True, "details": "ok"}],
            "advanced": [],
            "optional": [],
        },
    )
    monkeypatch.setattr(
        codex,
        "run_local_commands",
        lambda timeout_seconds=120: [
            {
                "command": "python -c import atena_launcher",
                "returncode": 0,
                "stdout": "ok",
                "stderr": "",
                "soft_failed": False,
                "soft_reason": "",
            },
            {
                "command": "python -c import main",
                "returncode": 1,
                "stdout": "",
                "stderr": "No module named 'numpy'",
                "soft_failed": True,
                "soft_reason": "advanced missing",
            },
        ],
    )

    diagnostic = codex.run_full_diagnostic(include_commands=True)

    assert diagnostic["status"] == "ok"


def test_run_advanced_autopilot_reports_soft_warning_and_advanced_missing(monkeypatch, tmp_path) -> None:
    codex = AtenaCodex(root_path=str(tmp_path))

    monkeypatch.setattr(
        codex,
        "run_full_diagnostic",
        lambda include_commands=True, timeout_seconds=120: {
            "status": "ok",
            "modules": {
                "essential": [{"name": "requests", "ok": True, "details": "ok"}],
                "advanced": [{"name": "numpy", "ok": False, "details": "missing"}],
                "optional": [],
            },
            "commands": [
                {
                    "command": "python -c import main",
                    "returncode": 1,
                    "stdout": "",
                    "stderr": "No module named 'numpy'",
                    "soft_failed": True,
                    "soft_reason": "advanced missing",
                }
            ],
        },
    )

    result = codex.run_advanced_autopilot(objective="test")

    assert result["status"] == "ok"
    assert result["missing_essential_modules"] == []
    assert result["missing_advanced_modules"] == ["numpy"]
    assert result["failing_commands_count"] == 0
    assert result["soft_warning_commands_count"] == 1
    assert any(item["title"] == "Eliminar soft-fails de import avançado" for item in result["action_plan"])
