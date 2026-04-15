#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from core import atena_launcher


def test_maybe_prepare_local_model_skips_non_llm_commands(monkeypatch):
    called = {"value": False}

    class _Router:
        def prepare_free_local_model(self):
            called["value"] = True
            return True, "ok"

    monkeypatch.setattr("core.atena_llm_router.AtenaLLMRouter", _Router)
    atena_launcher._maybe_prepare_local_model("doctor")
    assert called["value"] is False


def test_maybe_prepare_local_model_runs_for_start(monkeypatch, capsys):
    class _Router:
        def prepare_free_local_model(self):
            return True, "modelo pronto"

    monkeypatch.setattr("core.atena_llm_router.AtenaLLMRouter", _Router)
    monkeypatch.setenv("ATENA_AUTO_PREPARE_LOCAL_MODEL", "1")
    atena_launcher._maybe_prepare_local_model("start")
    out = capsys.readouterr().out
    assert "bootstrap-model:ok" in out
    assert "modelo pronto" in out


def test_maybe_prepare_local_model_can_be_disabled(monkeypatch):
    called = {"value": False}

    class _Router:
        def prepare_free_local_model(self):
            called["value"] = True
            return True, "ok"

    monkeypatch.setattr("core.atena_llm_router.AtenaLLMRouter", _Router)
    monkeypatch.setenv("ATENA_AUTO_PREPARE_LOCAL_MODEL", "0")
    atena_launcher._maybe_prepare_local_model("start")
    assert called["value"] is False
