#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Harness de avaliação contínua por perfil de cliente."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class HarnessResult:
    profile: str
    command: str
    returncode: int
    ok: bool


PROFILE_COMMANDS: dict[str, str] = {
    "support": "./atena doctor",
    "dev": "./atena modules-smoke",
    "ops": "./atena go-no-go",
    "security": "./atena guardian",
}


def run_profile(profile: str, timeout: int = 180) -> HarnessResult:
    cmd = PROFILE_COMMANDS.get(profile)
    if not cmd:
        return HarnessResult(profile=profile, command="", returncode=2, ok=False)
    proc = subprocess.run(cmd, shell=True, cwd=str(ROOT), capture_output=True, text=True, timeout=timeout)
    return HarnessResult(profile=profile, command=cmd, returncode=proc.returncode, ok=proc.returncode == 0)


def score_profiles(profiles: list[str]) -> dict[str, object]:
    results = [run_profile(p) for p in profiles]
    total = len(results)
    passed = sum(1 for r in results if r.ok)
    return {
        "total": total,
        "passed": passed,
        "score": round((passed / total) if total else 0.0, 4),
        "results": [r.__dict__ for r in results],
    }
