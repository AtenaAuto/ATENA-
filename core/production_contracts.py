#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Validação leve de contratos JSON dos comandos de produção."""

from __future__ import annotations

from typing import Any


REQUIRED_FIELDS: dict[str, set[str]] = {
    "policy-check": {"allowed", "requires_approval", "reason"},
    "telemetry-summary": {"total", "success_rate", "avg_latency_ms", "cost_units"},
    "tenant-report": {"tenant_id", "total", "success_rate", "avg_latency_ms", "cost_units", "month"},
    "slo-check": {"window_days", "thresholds", "summary", "checks", "status"},
    "quality-score": {"total", "passed", "score", "results", "baseline"},
    "skill-list": set(),
    "incident-drill": {"scenario", "primary_provider", "fallback_provider", "recovered", "timestamp"},
    "quota-check": {"quota", "usage", "checks", "status"},
}


def validate_contract(command: str, payload: Any) -> list[str]:
    required = REQUIRED_FIELDS.get(command)
    if required is None:
        return []
    if not isinstance(payload, dict) and command != "skill-list":
        return ["payload must be an object"]
    if command == "skill-list" and not isinstance(payload, list):
        return ["payload must be an array"]
    if isinstance(payload, dict):
        missing = [k for k in required if k not in payload]
        return [f"missing field: {k}" for k in missing]
    return []
