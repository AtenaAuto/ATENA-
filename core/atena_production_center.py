#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CLI de integração dos módulos de produção da ATENA."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.heavy_mode_selector import choose_mode
from core.production_guardrails import Action, PolicyEngine, Role
from core.production_observability import TelemetryStore
from core.production_onboarding import run_onboarding
from core.production_quality_harness import score_profiles
from core.skill_marketplace import SkillMarketplace, SkillRecord

EVOLUTION = ROOT / "atena_evolution" / "production_center"
EVOLUTION.mkdir(parents=True, exist_ok=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="ATENA Production Center")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_policy = sub.add_parser("policy-check", help="Valida role/action")
    p_policy.add_argument("--role", required=True, choices=[r.value for r in Role])
    p_policy.add_argument("--action", required=True, choices=[a.value for a in Action])

    p_tlog = sub.add_parser("telemetry-log", help="Registra evento de telemetria")
    p_tlog.add_argument("--mission", required=True)
    p_tlog.add_argument("--status", required=True)
    p_tlog.add_argument("--latency-ms", required=True, type=int)
    p_tlog.add_argument("--cost", required=True, type=float)

    sub.add_parser("telemetry-summary", help="Resumo de telemetria")

    p_quality = sub.add_parser("quality-score", help="Scoring por perfis")
    p_quality.add_argument("--profiles", default="support,dev,ops,security")

    sub.add_parser("onboarding-run", help="Executa onboarding profissional")

    p_sreg = sub.add_parser("skill-register", help="Registra skill")
    p_sreg.add_argument("--id", required=True)
    p_sreg.add_argument("--version", default="1.0.0")
    p_sreg.add_argument("--risk", default="medium")
    p_sreg.add_argument("--cost-class", default="standard")
    p_sreg.add_argument("--compat", default=">=3.2.0")

    p_sap = sub.add_parser("skill-approve", help="Aprova skill")
    p_sap.add_argument("--id", required=True)
    sub.add_parser("skill-list", help="Lista skills")

    p_mode = sub.add_parser("mode-select", help="Seleciona modo leve/pesado")
    p_mode.add_argument("--complexity", type=int, required=True)
    p_mode.add_argument("--budget", type=float, required=True)
    p_mode.add_argument("--latency-sensitive", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    telemetry = TelemetryStore(EVOLUTION / "telemetry.jsonl")
    market = SkillMarketplace(EVOLUTION / "skills_catalog.json")
    policy = PolicyEngine()

    if args.cmd == "policy-check":
        decision = policy.decide(Role(args.role), Action(args.action))
        print(json.dumps(decision.__dict__, ensure_ascii=False, indent=2))
        return 0 if decision.allowed else 2

    if args.cmd == "telemetry-log":
        event = telemetry.append(args.mission, args.status, args.latency_ms, args.cost)
        print(json.dumps(event.__dict__, ensure_ascii=False, indent=2))
        return 0

    if args.cmd == "telemetry-summary":
        print(json.dumps(telemetry.summarize(), ensure_ascii=False, indent=2))
        return 0

    if args.cmd == "quality-score":
        profiles = [p.strip() for p in args.profiles.split(",") if p.strip()]
        payload = score_profiles(profiles)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0 if float(payload.get("score", 0.0)) >= 0.5 else 2

    if args.cmd == "onboarding-run":
        payload = run_onboarding()
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0 if payload["status"] == "ok" else 2

    if args.cmd == "skill-register":
        market.register(
            SkillRecord(
                skill_id=args.id,
                version=args.version,
                risk_level=args.risk,
                cost_class=args.cost_class,
                compatible_with=args.compat,
            )
        )
        print(json.dumps({"status": "registered", "id": args.id}, ensure_ascii=False, indent=2))
        return 0

    if args.cmd == "skill-approve":
        ok = market.approve(args.id)
        print(json.dumps({"status": "approved" if ok else "not-found", "id": args.id}, ensure_ascii=False, indent=2))
        return 0 if ok else 2

    if args.cmd == "skill-list":
        print(json.dumps(market.list_records(), ensure_ascii=False, indent=2))
        return 0

    if args.cmd == "mode-select":
        decision = choose_mode(args.complexity, args.budget, args.latency_sensitive)
        print(json.dumps(decision.__dict__, ensure_ascii=False, indent=2))
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
