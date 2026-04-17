#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Missão: ciclo vivo (aprende na internet, cria, executa e testa)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.atena_digital_organism_live_cycle import run_live_cycle, run_live_cycles, run_live_daemon


def main() -> int:
    parser = argparse.ArgumentParser(description="Executa live cycle de organismo digital")
    parser.add_argument("--topic", default="autonomous ai engineering", help="Tópico para aprendizado na internet")
    parser.add_argument("--iterations", type=int, default=1, help="Quantidade de ciclos autônomos encadeados")
    parser.add_argument("--batches", type=int, default=1, help="Quantidade de batches autônomas em modo daemon")
    parser.add_argument(
        "--recovery-attempts",
        type=int,
        default=1,
        help="Tentativas de auto-recuperação com tipo alternativo quando execução falhar",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Falha se a batch não demonstrar aprendizado consistente",
    )
    args = parser.parse_args()

    if args.batches > 1:
        payload = run_live_daemon(
            ROOT,
            seed_topic=args.topic,
            batches=args.batches,
            iterations_per_batch=args.iterations,
            strict=args.strict,
        )
        summary = payload["summary"]
        print("🧬 ATENA Digital Organism Daemon")
        print(f"seed_topic={summary['seed_topic']}")
        print(f"final_topic={summary['final_topic']}")
        print(f"batches={summary['batches']}")
        print(f"iterations_per_batch={summary['iterations_per_batch']}")
        print(f"status={summary['status']}")
        print(f"avg_success_rate={summary['avg_success_rate']}")
        print(f"all_batches_consistently_learning={summary['all_batches_consistently_learning']}")
        print(f"json={summary['daemon_json']}")
        print(f"markdown={summary['daemon_markdown']}")
        return 0 if summary["status"] == "ok" else 2

    if args.iterations > 1:
        payload = run_live_cycles(ROOT, seed_topic=args.topic, iterations=args.iterations, strict=args.strict)
        summary = payload["summary"]
        print("🧠⚙️🧪 ATENA Digital Organism Live Batch")
        print(f"seed_topic={summary['seed_topic']}")
        print(f"iterations={summary['iterations']}")
        print(f"status={summary['status']}")
        print(f"success_rate={summary['success_rate']}")
        print(f"avg_learning_confidence={summary['avg_learning_confidence']}")
        print(f"consistently_learning={summary['consistently_learning']}")
        print(f"json={summary['batch_json']}")
        print(f"markdown={summary['batch_markdown']}")
        return 0 if summary["status"] == "ok" else 2

    payload = run_live_cycle(ROOT, topic=args.topic, max_recovery_attempts=max(0, args.recovery_attempts))
    print("🧠⚙️🧪 ATENA Digital Organism Live Cycle")
    print(f"topic={payload['topic']}")
    print(f"status={payload['status']}")
    print(f"project_type={payload['build']['project_type']}")
    print(f"build_ok={payload['build']['ok']}")
    print(f"execution_ok={payload['execution']['ok']}")
    print(f"recovery_used={payload.get('recovery_used', False)}")
    print(f"memory={payload['memory_path']}")
    print(f"json={payload['json_path']}")
    print(f"markdown={payload['markdown_path']}")
    return 0 if payload["status"] == "ok" else 2


if __name__ == "__main__":
    raise SystemExit(main())
