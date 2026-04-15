#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from protocols.atena_internet_challenge_mission import _build_report, _score_source


def test_score_source_counts_ok_and_payload_density():
    src = {
        "source": "github",
        "ok": True,
        "details": {"top_repos": [{"name": "a"}, {"name": "b"}], "note": "strong signal"},
    }
    score = _score_source(src)
    assert score >= 12


def test_build_report_contains_ranked_sources_and_json():
    payload = {
        "topic": "agentic ai evals",
        "status": "ok",
        "confidence": 1.0,
        "recommendation": "seguir",
        "sources": [
            {"source": "wikipedia", "ok": True, "details": {"extract": "abc"}},
            {"source": "github", "ok": True, "details": {"top_repos": [{"a": 1}, {"b": 2}]}},
        ],
    }
    report = _build_report(payload)
    assert "ATENA Internet Challenge" in report
    assert "Ranked Sources" in report
    assert "Raw JSON" in report
