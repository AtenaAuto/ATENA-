#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Checks objetivos para liberar operação de produção."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from core.production_observability import TelemetryStore
from core.skill_marketplace import SkillMarketplace


@dataclass(frozen=True)
class ReadinessCheck:
    name: str
    ok: bool
    details: str
    level: str = "required"


def run_readiness(
    *,
    telemetry: TelemetryStore,
    market: SkillMarketplace,
    evolution_dir: Path,
    min_success_rate: float = 0.7,
) -> dict[str, object]:
    checks: list[ReadinessCheck] = []

    telemetry_summary = telemetry.summarize()
    checks.append(
        ReadinessCheck(
            name="telemetry_events_present",
            ok=telemetry_summary["total"] > 0,
            details=f"total_events={telemetry_summary['total']}",
            level="warning",
        )
    )

    slo = telemetry.slo_check(
        min_success_rate=min_success_rate,
        max_avg_latency_ms=1200,
        max_cost_units=500.0,
        window_days=30,
    )
    checks.append(
        ReadinessCheck(
            name="slo_baseline",
            ok=slo["status"] == "ok",
            details=f"status={slo['status']} severity={slo['alert']['severity']}",
        )
    )

    records = market.list_records()
    has_active_approved = any(r.get("active") and r.get("approved") for r in records)
    checks.append(
        ReadinessCheck(
            name="approved_active_skill",
            ok=has_active_approved,
            details="at least one active approved skill is required",
        )
    )

    audit_file = evolution_dir / "policy_audit.jsonl"
    checks.append(
        ReadinessCheck(
            name="policy_audit_enabled",
            ok=audit_file.exists(),
            details=f"audit_file={audit_file.name}",
            level="warning",
        )
    )

    required_failures = [c for c in checks if c.level == "required" and not c.ok]
    warning_failures = [c for c in checks if c.level == "warning" and not c.ok]

    if required_failures:
        status = "fail"
    elif warning_failures:
        status = "warn"
    else:
        status = "pass"

    return {
        "status": status,
        "checks": [c.__dict__ for c in checks],
        "summary": {
            "required_failures": len(required_failures),
            "warning_failures": len(warning_failures),
            "total_checks": len(checks),
        },
    }
