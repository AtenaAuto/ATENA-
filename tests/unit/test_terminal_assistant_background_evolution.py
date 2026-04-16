#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from core.atena_terminal_assistant import (
    EvolutionState,
    choose_next_background_topic,
    get_evolution_status,
    rank_topics_for_background,
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


def test_rank_topics_for_background_prioritizes_low_coverage():
    topics = ["topic-a", "topic-b"]
    events = [{"event": "background_internet_learning", "topic": "topic-a", "confidence": 0.9}]
    ranked = rank_topics_for_background(topics, events)
    assert ranked[0][0] == "topic-b"


def test_choose_next_background_topic_uses_ranking(monkeypatch):
    state = EvolutionState()
    monkeypatch.setattr(
        "core.atena_terminal_assistant.load_recent_background_events",
        lambda limit=500: [{"event": "background_internet_learning", "topic": "topic-a", "confidence": 0.9}],
    )
    chosen = choose_next_background_topic(state, ["topic-a", "topic-b"])
    assert chosen == "topic-b"
