#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from core.atena_terminal_assistant import run_background_internet_learning_cycle


def test_background_internet_learning_cycle_records_payload(monkeypatch):
    monkeypatch.setattr(
        "core.atena_terminal_assistant.run_internet_challenge",
        lambda topic: {"status": "ok", "confidence": 0.9, "sources": [{"source": "x"}], "topic": topic},
    )
    recorded = {}

    def _fake_append(entry):
        recorded.update(entry)

    monkeypatch.setattr("core.atena_terminal_assistant.append_learning_memory", _fake_append)
    payload = run_background_internet_learning_cycle("agentic reliability")
    assert payload["status"] == "ok"
    assert recorded["event"] == "background_internet_learning"
    assert recorded["sources"] == 1
