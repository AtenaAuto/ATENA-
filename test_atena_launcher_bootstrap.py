#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from types import SimpleNamespace

from core import atena_launcher


def test_launcher_runs_bootstrap_and_prepare_before_assistant(monkeypatch):
    calls = []

    def _fake_run(cmd, cwd=None, check=False, env=None, timeout=None):
        calls.append({"cmd": cmd, "cwd": cwd, "check": check, "env": env, "timeout": timeout})
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(atena_launcher.subprocess, "run", _fake_run)
    monkeypatch.setenv("ATENA_AUTO_BOOTSTRAP", "1")
    monkeypatch.setenv("ATENA_AUTO_PREPARE_LOCAL_MODEL", "1")

    rc = atena_launcher.main(["./atena", "assistant"])

    assert rc == 0
    assert len(calls) == 3
    assert calls[0]["cmd"][1].endswith("core/atena_env_bootstrap.py")
    assert calls[0]["timeout"] == 180
    assert calls[1]["cmd"][1] == "-c"
    assert calls[1]["timeout"] == 300
    assert calls[2]["cmd"][1].endswith("core/atena_terminal_assistant.py")
    assert calls[2]["env"]["ATENA_AUTO_PREPARE_LOCAL_MODEL"] == "0"


def test_launcher_aborts_when_strict_bootstrap_fails(monkeypatch):
    calls = []

    def _fake_run(cmd, cwd=None, check=False, env=None, timeout=None):
        calls.append({"cmd": cmd, "cwd": cwd, "check": check, "env": env, "timeout": timeout})
        # Falha apenas no bootstrap
        if cmd[1].endswith("core/atena_env_bootstrap.py"):
            return SimpleNamespace(returncode=2)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(atena_launcher.subprocess, "run", _fake_run)
    monkeypatch.setenv("ATENA_AUTO_BOOTSTRAP", "1")
    monkeypatch.setenv("ATENA_STRICT_BOOTSTRAP", "1")

    rc = atena_launcher.main(["./atena", "assistant"])

    assert rc == 2
    # Deve parar no bootstrap sem chamar prepare/assistant
    assert len(calls) == 1


def test_launcher_executes_enterprise_readiness_command(monkeypatch):
    calls = []

    def _fake_run(cmd, cwd=None, check=False, env=None, timeout=None):
        calls.append({"cmd": cmd, "cwd": cwd, "check": check, "env": env, "timeout": timeout})
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(atena_launcher.subprocess, "run", _fake_run)
    monkeypatch.setenv("ATENA_AUTO_BOOTSTRAP", "0")

    rc = atena_launcher.main(["./atena", "enterprise-readiness", "--pilots", "5"])

    assert rc == 0
    assert len(calls) == 1
    assert calls[0]["cmd"][1].endswith("protocols/atena_enterprise_readiness_mission.py")
    assert calls[0]["cmd"][2:] == ["--pilots", "5"]


def test_launcher_executes_enterprise_advanced_command(monkeypatch):
    calls = []

    def _fake_run(cmd, cwd=None, check=False, env=None, timeout=None):
        calls.append({"cmd": cmd, "cwd": cwd, "check": check, "env": env, "timeout": timeout})
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(atena_launcher.subprocess, "run", _fake_run)
    monkeypatch.setenv("ATENA_AUTO_BOOTSTRAP", "0")

    rc = atena_launcher.main(["./atena", "enterprise-advanced", "--tenant", "corp-a"])

    assert rc == 0
    assert len(calls) == 1
    assert calls[0]["cmd"][1].endswith("protocols/atena_enterprise_advanced_mission.py")
    assert calls[0]["cmd"][2:] == ["--tenant", "corp-a"]


def test_launcher_executes_secret_scan_command(monkeypatch):
    calls = []

    def _fake_run(cmd, cwd=None, check=False, env=None, timeout=None):
        calls.append({"cmd": cmd, "cwd": cwd, "check": check, "env": env, "timeout": timeout})
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(atena_launcher.subprocess, "run", _fake_run)
    monkeypatch.setenv("ATENA_AUTO_BOOTSTRAP", "0")

    rc = atena_launcher.main(["./atena", "secret-scan"])

    assert rc == 0
    assert len(calls) == 1
    assert calls[0]["cmd"][1].endswith("core/atena_secret_scan.py")
