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
    assert payload["contract_valid"] is True

    m = run_cli("mode-select", "--complexity", "9", "--budget", "5")
    assert m.returncode == 0
    decision = json.loads(m.stdout)
    assert decision["mode"] in {"light", "heavy"}


def test_skill_catalog_telemetry_and_resilience_flow():
    sid = "test-skill-prod-center"
    reg_1 = run_cli("skill-register", "--id", sid, "--version", "1.2.3")
    assert reg_1.returncode == 0
    reg_2 = run_cli("skill-register", "--id", sid, "--version", "1.2.4")
    assert reg_2.returncode == 0

    app = run_cli("skill-approve", "--id", sid, "--version", "1.2.4")
    assert app.returncode == 0

    promote = run_cli("skill-promote", "--id", sid, "--version", "1.2.4")
    assert promote.returncode == 0

    rollback = run_cli("skill-rollback", "--id", sid, "--to-version", "1.2.4")
    assert rollback.returncode == 0

    listed = run_cli("skill-list")
    assert listed.returncode == 0
    data = json.loads(listed.stdout)
    target = [x for x in data if x.get("skill_id") == sid and x.get("version") == "1.2.4"]
    assert target and target[0]["approved"] is True and target[0]["active"] is True

    tlog = run_cli(
        "telemetry-log",
        "--mission",
        "demo",
        "--status",
        "ok",
        "--latency-ms",
        "120",
        "--cost",
        "0.2",
        "--tenant",
        "tenant-cli",
    )
    assert tlog.returncode == 0

    tsum = run_cli("telemetry-summary")
    assert tsum.returncode == 0
    summary = json.loads(tsum.stdout)
    assert summary["total"] >= 1

    tenant_report = run_cli("tenant-report", "--tenant", "tenant-cli", "--month", "2026-04")
    assert tenant_report.returncode == 0
    tenant_payload = json.loads(tenant_report.stdout)
    assert tenant_payload["tenant_id"] == "tenant-cli"

    slo = run_cli("slo-check", "--window-days", "30", "--min-success-rate", "0.1", "--max-avg-latency-ms", "1000", "--max-cost-units", "100")
    assert slo.returncode == 0
    slo_payload = json.loads(slo.stdout)
    assert slo_payload["status"] == "ok"
    assert "alert" in slo_payload

    drill = run_cli("incident-drill", "--scenario", "provider-outage")
    assert drill.returncode == 0
    drill_payload = json.loads(drill.stdout)
    assert drill_payload["recovered"] is True


def test_quota_check_command():
    quota = run_cli("quota-check", "--rpm", "80", "--parallel-jobs", "2", "--storage-mb", "300")
    assert quota.returncode == 0
    payload = json.loads(quota.stdout)
    assert payload["status"] == "ok"
    assert payload["contract_valid"] is True


def test_production_ready_command():
    proc = run_cli("production-ready")
    assert proc.returncode in {0, 2}
    payload = json.loads(proc.stdout)
    assert payload["status"] in {"pass", "warn", "fail"}
    assert payload["contract_valid"] is True
    assert "checks" in payload


def test_remediation_plan_command():
    proc = run_cli("remediation-plan")
    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    assert payload["contract_valid"] is True
    assert "actions" in payload


def test_perfection_plan_command():
    proc = run_cli("perfection-plan")
    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    assert payload["contract_valid"] is True
    assert payload["status"] == "in-progress"


def test_internet_challenge_command():
    proc = run_cli("internet-challenge", "--topic", "artificial intelligence")
    assert proc.returncode in {0, 2}
    payload = json.loads(proc.stdout)
    assert payload["contract_valid"] is True
    assert "sources" in payload
