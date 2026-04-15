#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from protocols.atena_advanced_assessment_mission import _recommendations


def test_recommendations_include_eval_harness():
    recs = _recommendations(
        module_smoke={"status": "ok"},
        prod_gate={"status": "APROVADO"},
        internet={"confidence": 0.8},
    )
    assert any("eval harness avançado" in item for item in recs)
    assert len(recs) >= 5


def test_recommendations_handle_low_confidence_and_failures():
    recs = _recommendations(
        module_smoke={"status": "failed"},
        prod_gate={"status": "failed"},
        internet={"confidence": 0.2},
    )
    assert any("Aumentar robustez de coleta web" in item for item in recs)
    assert any("rollback automatizado" in item for item in recs)
