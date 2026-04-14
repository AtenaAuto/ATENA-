import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CLI = ROOT / "core" / "atena_production_center.py"


def run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(CLI), *args],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )


def test_policy_check_and_mode_select():
    p = run_cli("policy-check", "--role", "operator", "--action", "open_url")
    assert p.returncode == 0
    payload = json.loads(p.stdout)
    assert payload["allowed"] is True
    assert payload["requires_approval"] is True

    m = run_cli("mode-select", "--complexity", "9", "--budget", "5")
    assert m.returncode == 0
    decision = json.loads(m.stdout)
    assert decision["mode"] in {"light", "heavy"}


def test_skill_catalog_and_telemetry_flow():
    sid = "test-skill-prod-center"
    reg = run_cli("skill-register", "--id", sid, "--version", "1.2.3")
    assert reg.returncode == 0

    app = run_cli("skill-approve", "--id", sid)
    assert app.returncode == 0

    listed = run_cli("skill-list")
    assert listed.returncode == 0
    data = json.loads(listed.stdout)
    target = [x for x in data if x.get("skill_id") == sid]
    assert target and target[0]["approved"] is True

    tlog = run_cli("telemetry-log", "--mission", "demo", "--status", "ok", "--latency-ms", "120", "--cost", "0.2")
    assert tlog.returncode == 0
    tsum = run_cli("telemetry-summary")
    assert tsum.returncode == 0
    summary = json.loads(tsum.stdout)
    assert summary["total"] >= 1
