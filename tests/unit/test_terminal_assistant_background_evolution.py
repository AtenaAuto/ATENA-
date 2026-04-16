#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from core.atena_terminal_assistant import (
    EvolutionState,
    get_evolution_status,
    parse_background_topics,
    run_background_internet_learning_cycle,
)


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


def test_parse_background_topics_defaults_and_custom():
    defaults = parse_background_topics(None)
    assert len(defaults) >= 2
    custom = parse_background_topics("topic a, topic b")
    assert custom == ["topic a", "topic b"]


def test_get_evolution_status_contains_core_fields():
    state = EvolutionState(cycles=3, last_success=True, last_error=None)
    status = get_evolution_status(state)
    assert "cycles=3" in status
    assert "last_success=True" in status
