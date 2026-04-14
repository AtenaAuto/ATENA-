#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Telemetria/observabilidade operacional para ATENA."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass(frozen=True)
class TelemetryEvent:
    mission: str
    status: str
    latency_ms: int
    cost_units: float
    timestamp: str


class TelemetryStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, mission: str, status: str, latency_ms: int, cost_units: float) -> TelemetryEvent:
        event = TelemetryEvent(
            mission=mission,
            status=status,
            latency_ms=latency_ms,
            cost_units=cost_units,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(event), ensure_ascii=False) + "\n")
        return event

    def summarize(self) -> dict[str, float]:
        if not self.path.exists():
            return {"total": 0, "success_rate": 0.0, "avg_latency_ms": 0.0, "cost_units": 0.0}
        lines = [json.loads(line) for line in self.path.read_text(encoding="utf-8").splitlines() if line.strip()]
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
