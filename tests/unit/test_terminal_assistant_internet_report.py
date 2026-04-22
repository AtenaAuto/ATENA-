#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from core import atena_terminal_assistant as ta


def test_is_internet_request_detects_report_request():
    assert ta._is_internet_request("Me dá um relatório completo da internet sobre IA") is True


def test_extract_internet_topic_from_complete_report_prompt():
    topic = ta._extract_internet_topic(
        "Pesquise na internet e entregue um relatório completo sobre ai agent safety benchmarks 2026"
    )
    assert topic == "ai agent safety benchmarks 2026"


def test_run_user_internet_research_returns_complete_report(monkeypatch):
    monkeypatch.setattr(
        ta,
        "run_internet_challenge",
        lambda topic: {
            "status": "ok",
            "weighted_confidence": 0.88,
            "recommendation": "Consolidar síntese final",
            "all_sources": [
                {
                    "source": "github",
                    "ok": True,
                    "quality_score": 0.91,
                    "details": {"top_repos": [{"full_name": "org/agent-framework"}]},
                },
                {
                    "source": "crossref",
                    "ok": False,
                    "quality_score": 0.0,
                    "details": {"error": "timeout"},
                },
            ],
            "synthesis": {
                "coverage_summary": "1/2 fontes responderam",
                "next_action": "Refinar a query",
                "release_risk": "medium",
            },
        },
    )

    report = ta.run_user_internet_research("pesquise na internet sobre ai agents")

    assert "Resultado da pesquisa" in report
    assert "org/agent-framework" in report
    assert "crossref" not in report
    assert "Fonte:" not in report


def test_run_user_internet_research_without_topic_guides_user():
    report = ta.run_user_internet_research("/internet")
    assert "Use `/internet <tema>`" in report
