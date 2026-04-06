#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from core.atena_pipeline import collect_multi_source_text, score_source_relevance


def test_score_source_relevance_prefers_official_repo():
    text = "ATENA orchestrator pipeline for AI agents in github."
    score = score_source_relevance("https://github.com/AtenaAuto/ATENA-", text, "ATENA architecture")
    assert score >= 0.5


def test_collect_multi_source_text_filters_irrelevant_sources(monkeypatch):
    def fake_fetch(url: str):
        if "relevant" in url:
            return True, "ATENA pipeline orchestrator github automation ai"
        return True, "random cooking recipe tomato basil cheese"

    monkeypatch.setattr("core.atena_pipeline.fetch_text_via_http", fake_fetch)
    ok, merged, stats = collect_multi_source_text(
        ["https://example.com/relevant", "https://example.com/noise"],
        objective="ATENA engineering insights",
    )
    assert ok is True
    assert "ATENA" in merged
    assert stats["successful_sources"] == 1
    assert stats["failed_sources"] == 1
