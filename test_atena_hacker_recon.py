#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from types import SimpleNamespace

from core import atena_hacker_recon


def test_hacker_recon_builds_main_command_and_json(monkeypatch, capsys, tmp_path):
    calls = []

    def _fake_run(cmd, cwd=None, text=None, capture_output=None, timeout=None):
        calls.append({"cmd": cmd, "cwd": cwd, "text": text, "capture_output": capture_output})
        return SimpleNamespace(returncode=0, stdout="ok\n", stderr="")

    monkeypatch.setattr(atena_hacker_recon.subprocess, "run", _fake_run)
    monkeypatch.setattr(atena_hacker_recon, "ROOT", tmp_path)
    monkeypatch.setattr(atena_hacker_recon, "MAIN_SCRIPT", tmp_path / "core" / "main.py")
    monkeypatch.setattr(atena_hacker_recon, "REPORTS_DIR", tmp_path / "analysis_reports")

    rc = atena_hacker_recon.run(
        ["--topic", "agentes ai", "--auto", "--cycles", "2", "--json", "--output-json", "analysis_reports/recon.json"]
    )

    captured = capsys.readouterr()
    assert rc == 0
    assert len(calls) == 1
    assert calls[0]["cmd"][2:] == ["--recon", "agentes ai", "--auto", "--cycles", "2"]
    assert '"ok": true' in captured.out
    assert '"recon_score":' in captured.out
    assert "Relatório salvo em:" in captured.out
    assert (tmp_path / "analysis_reports" / "recon.json").exists()


def test_hacker_recon_no_report(monkeypatch, tmp_path):
    def _fake_run(cmd, cwd=None, text=None, capture_output=None, timeout=None):
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(atena_hacker_recon.subprocess, "run", _fake_run)
    monkeypatch.setattr(atena_hacker_recon, "ROOT", tmp_path)
    monkeypatch.setattr(atena_hacker_recon, "MAIN_SCRIPT", tmp_path / "core" / "main.py")
    monkeypatch.setattr(atena_hacker_recon, "REPORTS_DIR", tmp_path / "analysis_reports")

    rc = atena_hacker_recon.run(["--topic", "x", "--no-report"])

    assert rc == 0
    assert not (tmp_path / "analysis_reports").exists()


def test_hacker_recon_timeout_returns_124(monkeypatch, tmp_path):
    def _fake_run(cmd, cwd=None, text=None, capture_output=None, timeout=None):
        raise atena_hacker_recon.subprocess.TimeoutExpired(cmd=cmd, timeout=timeout, output="partial", stderr="slow")

    monkeypatch.setattr(atena_hacker_recon.subprocess, "run", _fake_run)
    monkeypatch.setattr(atena_hacker_recon, "ROOT", tmp_path)
    monkeypatch.setattr(atena_hacker_recon, "MAIN_SCRIPT", tmp_path / "core" / "main.py")
    monkeypatch.setattr(atena_hacker_recon, "REPORTS_DIR", tmp_path / "analysis_reports")

    rc = atena_hacker_recon.run(["--topic", "x", "--timeout", "1", "--no-report"])

    assert rc == 124
