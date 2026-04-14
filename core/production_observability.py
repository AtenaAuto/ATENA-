#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Telemetria/observabilidade operacional para ATENA."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path


@dataclass(frozen=True)
class TelemetryEvent:
    mission: str
    status: str
    latency_ms: int
    cost_units: float
    timestamp: str
    tenant_id: str = "default"


class TelemetryStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(
        self,
        mission: str,
        status: str,
        latency_ms: int,
        cost_units: float,
        tenant_id: str = "default",
    ) -> TelemetryEvent:
        event = TelemetryEvent(
            mission=mission,
            status=status,
            latency_ms=latency_ms,
            cost_units=cost_units,
            timestamp=datetime.now(timezone.utc).isoformat(),
            tenant_id=tenant_id,
        )
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(event), ensure_ascii=False) + "\n")
        return event

    def _load_events(self) -> list[dict]:
        if not self.path.exists():
            return []
        return [json.loads(line) for line in self.path.read_text(encoding="utf-8").splitlines() if line.strip()]

    @staticmethod
    def _summarize_events(lines: list[dict]) -> dict[str, float]:
        total = len(lines)
        ok = sum(1 for l in lines if str(l.get("status", "")).lower() in {"ok", "success"})
        avg_latency = (sum(int(l.get("latency_ms", 0)) for l in lines) / total) if total else 0.0
        cost = sum(float(l.get("cost_units", 0.0)) for l in lines)
        return {
            "total": total,
            "success_rate": round((ok / total) if total else 0.0, 4),
            "avg_latency_ms": round(avg_latency, 2),
            "cost_units": round(cost, 4),
        }

    def summarize(self) -> dict[str, float]:
        return self._summarize_events(self._load_events())

    def summarize_by_tenant(self, tenant_id: str) -> dict[str, float]:
        lines = [l for l in self._load_events() if str(l.get("tenant_id", "default")) == tenant_id]
        payload = self._summarize_events(lines)
        payload["tenant_id"] = tenant_id
        return payload

    def summarize_since_days(self, days: int) -> dict[str, float]:
        cutoff = datetime.now(timezone.utc) - timedelta(days=max(0, days))
        lines = []
        for item in self._load_events():
            raw_ts = item.get("timestamp")
            if not raw_ts:
                continue
            try:
                ts = datetime.fromisoformat(str(raw_ts))
            except ValueError:
                continue
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            if ts >= cutoff:
                lines.append(item)
        return self._summarize_events(lines)

    def slo_check(self, *, min_success_rate: float, max_avg_latency_ms: int, max_cost_units: float, window_days: int) -> dict[str, object]:
        summary = self.summarize_since_days(window_days)
        checks = {
            "success_rate": summary["success_rate"] >= min_success_rate,
            "avg_latency_ms": summary["avg_latency_ms"] <= max_avg_latency_ms,
            "cost_units": summary["cost_units"] <= max_cost_units,
        }
        return {
            "window_days": window_days,
            "thresholds": {
                "min_success_rate": min_success_rate,
                "max_avg_latency_ms": max_avg_latency_ms,
                "max_cost_units": max_cost_units,
            },
            "summary": summary,
            "checks": checks,
            "status": "ok" if all(checks.values()) else "violated",
        }
