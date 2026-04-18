#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Wrapper avançado para executar Hacker Recon com saída estruturada."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAIN_SCRIPT = ROOT / "core" / "main.py"
REPORTS_DIR = ROOT / "analysis_reports"


def _build_main_args(args: argparse.Namespace) -> list[str]:
    cmd = [sys.executable, str(MAIN_SCRIPT), "--recon", args.topic]
    if args.auto:
        cmd.append("--auto")
    if args.cycles is not None:
        cmd.extend(["--cycles", str(args.cycles)])
    if args.deep:
        cmd.append("--deep")
    if args.checker:
        cmd.append("--checker")
    return cmd


def _write_report(cmd: list[str], rc: int, output: str, topic: str, duration_s: float, recon_score: int, timed_out: bool) -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d_%H%M%S")
    report = REPORTS_DIR / f"HACKER_RECON_{ts}.md"
    tail = "\n".join(output.strip().splitlines()[-40:]) if output.strip() else "(sem saída capturada)"
    report.write_text(
        "\n".join(
            [
                "# ATENA Hacker Recon Report",
                "",
                f"- Timestamp (UTC): {dt.datetime.now(dt.timezone.utc).isoformat()}",
                f"- Topic: `{topic}`",
                f"- Exit code: `{rc}`",
                f"- Duration (s): `{duration_s}`",
                f"- Timed out: `{timed_out}`",
                f"- Recon score: `{recon_score}/100`",
                f"- Command: `{' '.join(cmd)}`",
                "",
                "## Output (tail)",
                "```text",
                tail,
                "```",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return report


def _compute_recon_score(output: str, rc: int) -> int:
    """Score simples (0-100) para sinalizar qualidade da execução de recon."""
    score = 0
    if rc == 0:
        score += 40
    lowered = output.lower()
    if "recon:" in lowered:
        score += 20
    if "dashboard dispon" in lowered:
        score += 10
    if "modelo de embedding carregado" in lowered:
        score += 10
    if "error" not in lowered and "traceback" not in lowered:
        score += 20
    return max(0, min(100, score))


def run(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Executa o Hacker Recon da ATENA com opções avançadas.")
    parser.add_argument("--topic", required=True, help="Tópico para o recon.")
    parser.add_argument("--auto", action="store_true", help="Ativa modo autônomo no core.")
    parser.add_argument("--cycles", type=int, default=None, help="Número de ciclos quando --auto estiver ativo.")
    parser.add_argument("--deep", action="store_true", help="Ativa self-mod profundo no core.")
    parser.add_argument("--checker", action="store_true", help="Ativa checker evolve no core.")
    parser.add_argument("--json", action="store_true", help="Exibe resumo final em JSON.")
    parser.add_argument("--output-json", default=None, help="Salva resumo JSON em arquivo.")
    parser.add_argument("--no-report", action="store_true", help="Não salvar relatório em analysis_reports/.")
    parser.add_argument("--timeout", type=int, default=180, help="Timeout máximo da execução em segundos.")
    args = parser.parse_args(argv)

    cmd = _build_main_args(args)
    started = time.time()
    try:
        proc = subprocess.run(cmd, cwd=str(ROOT), text=True, capture_output=True, timeout=args.timeout)
        timed_out = False
    except subprocess.TimeoutExpired as exc:
        proc = subprocess.CompletedProcess(exc.cmd, returncode=124, stdout=exc.stdout or "", stderr=(exc.stderr or "") + "\nTimeout excedido.")
        timed_out = True
    elapsed_s = round(time.time() - started, 3)

    if proc.stdout:
        print(proc.stdout, end="")
    if proc.stderr:
        print(proc.stderr, end="", file=sys.stderr)

    recon_score = _compute_recon_score(f"{proc.stdout}\n{proc.stderr}", proc.returncode)
    report_path = None
    if not args.no_report:
        report_path = _write_report(
            cmd,
            proc.returncode,
            f"{proc.stdout}\n{proc.stderr}",
            args.topic,
            elapsed_s,
            recon_score,
            timed_out,
        )
        try:
            report_label = str(report_path.relative_to(ROOT))
        except ValueError:
            report_label = str(report_path)
        print(f"📝 Relatório salvo em: {report_label}")

    if args.json:
        if report_path:
            try:
                report_json_path = str(report_path.relative_to(ROOT))
            except ValueError:
                report_json_path = str(report_path)
        else:
            report_json_path = None
        summary = {
            "ok": proc.returncode == 0,
            "exit_code": proc.returncode,
            "topic": args.topic,
            "command": cmd,
            "report_path": report_json_path,
            "timed_out": timed_out,
            "duration_s": elapsed_s,
            "recon_score": recon_score,
        }
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        summary = {
            "ok": proc.returncode == 0,
            "exit_code": proc.returncode,
            "topic": args.topic,
            "command": cmd,
            "report_path": str(report_path) if report_path else None,
            "timed_out": timed_out,
            "duration_s": elapsed_s,
            "recon_score": recon_score,
        }

    if args.output_json:
        output_json_path = Path(args.output_json)
        if not output_json_path.is_absolute():
            output_json_path = ROOT / output_json_path
        output_json_path.parent.mkdir(parents=True, exist_ok=True)
        output_json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"🧾 JSON salvo em: {output_json_path}")

    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(run(sys.argv[1:]))
