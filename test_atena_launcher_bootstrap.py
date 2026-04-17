#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from types import SimpleNamespace

from core import atena_launcher


def test_launcher_runs_bootstrap_and_prepare_before_assistant(monkeypatch):
    calls = []

    def _fake_run(cmd, cwd=None, check=False, env=None):
        calls.append({"cmd": cmd, "cwd": cwd, "check": check, "env": env})
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(atena_launcher.subprocess, "run", _fake_run)
    monkeypatch.setenv("ATENA_AUTO_BOOTSTRAP", "1")
    monkeypatch.setenv("ATENA_AUTO_PREPARE_LOCAL_MODEL", "1")

    rc = atena_launcher.main(["./atena", "assistant"])

    assert rc == 0
    assert len(calls) == 3
    assert calls[0]["cmd"][1].endswith("core/atena_env_bootstrap.py")
    assert calls[1]["cmd"][1] == "-c"
    assert calls[2]["cmd"][1].endswith("core/atena_terminal_assistant.py")
    assert calls[2]["env"]["ATENA_AUTO_PREPARE_LOCAL_MODEL"] == "0"
