#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
from pathlib import Path

from core.atena_digital_organism_live_cycle import _pick_project_type, run_live_cycle


def test_pick_project_type_prefers_api_when_sources_strong():
    payload = {
        "weighted_confidence": 0.81,
        "sources": [
            {"source": "github", "quality_score": 0.8},
            {"source": "npm", "quality_score": 0.71},
        ],
    }
    assert _pick_project_type(payload) == "api"


def test_run_live_cycle_creates_memory_and_artifacts(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(
        "core.atena_digital_organism_live_cycle.run_internet_challenge",
        lambda topic: {
            "status": "ok",
            "confidence": 0.9,
            "weighted_confidence": 0.75,
            "source_count": 3,
            "recommendation": "triangulate",
            "sources": [{"source": "github", "quality_score": 0.8}],
        },
    )

    payload = run_live_cycle(tmp_path, "autonomous coding")

    assert payload["build"]["ok"] is True
    assert payload["execution"]["ok"] is True
    assert Path(payload["memory_path"]).exists()
    assert Path(payload["json_path"]).exists()
    assert Path(payload["markdown_path"]).exists()

    memory_lines = Path(payload["memory_path"]).read_text(encoding="utf-8").strip().splitlines()
    assert memory_lines
    last = json.loads(memory_lines[-1])
    assert last["topic"] == "autonomous coding"
