#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""FastAPI de produção para expor recursos do production-center (Render-ready)."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from core.internet_challenge import run_internet_challenge
from core.production_gate import evaluate_go_live
from core.production_observability import TelemetryStore, dispatch_alert
from core.production_programming_probe import run_programming_probe
from core.production_readiness import build_remediation_plan, run_readiness
from core.skill_marketplace import SkillMarketplace

ROOT = Path(__file__).resolve().parent.parent
EVOLUTION = ROOT / "atena_evolution" / "production_center"
EVOLUTION.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="ATENA Production API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class InternetChallengeRequest(BaseModel):
    topic: str


class SLORequest(BaseModel):
    window_days: int = 30
    min_success_rate: float = 0.95
    max_avg_latency_ms: int = 500
    max_cost_units: float = 100.0
    webhook_url: str | None = None


class ProgrammingProbeRequest(BaseModel):
    prefix: str = "api_probe"
    site_template: str = "dashboard"


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/production/ready")
def production_ready() -> dict[str, object]:
    telemetry = TelemetryStore(EVOLUTION / "telemetry.jsonl")
    market = SkillMarketplace(EVOLUTION / "skills_catalog.json")
    return run_readiness(telemetry=telemetry, market=market, evolution_dir=EVOLUTION)


@app.get("/production/gate")
def production_gate(
    window_days: int = 30,
    min_success_rate: float = 0.95,
    max_avg_latency_ms: int = 500,
    max_cost_units: float = 100.0,
) -> dict[str, object]:
    telemetry = TelemetryStore(EVOLUTION / "telemetry.jsonl")
    market = SkillMarketplace(EVOLUTION / "skills_catalog.json")
    readiness = run_readiness(telemetry=telemetry, market=market, evolution_dir=EVOLUTION)
    remediation = build_remediation_plan(readiness)
    slo = telemetry.slo_check(
        min_success_rate=min_success_rate,
        max_avg_latency_ms=max_avg_latency_ms,
        max_cost_units=max_cost_units,
        window_days=window_days,
    )
    return evaluate_go_live(readiness=readiness, remediation=remediation, slo_alert=slo)


@app.post("/production/slo-alert")
def production_slo_alert(payload: SLORequest) -> dict[str, object]:
    telemetry = TelemetryStore(EVOLUTION / "telemetry.jsonl")
    slo = telemetry.slo_check(
        min_success_rate=payload.min_success_rate,
        max_avg_latency_ms=payload.max_avg_latency_ms,
        max_cost_units=payload.max_cost_units,
        window_days=payload.window_days,
    )
    delivery: dict[str, object] = {"sent": False, "reason": "webhook not provided"}
    if payload.webhook_url:
        delivery = dispatch_alert(payload.webhook_url, slo, state_path=EVOLUTION / "alerts_dedupe.json")
    return {
        "status": slo["status"],
        "alert": slo["alert"],
        "sent": bool(delivery.get("sent", False)),
        "delivery": delivery,
    }


@app.post("/production/internet-challenge")
def production_internet_challenge(payload: InternetChallengeRequest) -> dict[str, object]:
    return run_internet_challenge(payload.topic)


@app.post("/production/programming-probe")
def production_programming_probe(payload: ProgrammingProbeRequest) -> dict[str, object]:
    return run_programming_probe(ROOT, prefix=payload.prefix, site_template=payload.site_template)
