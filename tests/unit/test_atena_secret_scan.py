from __future__ import annotations

from pathlib import Path

from core.atena_secret_scan import scan_repo


def test_secret_scan_detects_github_token(tmp_path: Path):
    sample = tmp_path / "sample.py"
    sample.write_text('TOKEN = "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ123456"\n', encoding="utf-8")

    findings = scan_repo(tmp_path)

    assert findings
    assert findings[0]["file"] == "sample.py"
    assert findings[0]["pattern"] == "github_classic"


def test_secret_scan_ignores_safe_content(tmp_path: Path):
    sample = tmp_path / "safe.md"
    sample.write_text("sem segredos aqui\n", encoding="utf-8")

    findings = scan_repo(tmp_path)

    assert findings == []


def test_secret_scan_ignores_tests_by_default(tmp_path: Path):
    tests_dir = tmp_path / "tests" / "unit"
    tests_dir.mkdir(parents=True)
    sample = tests_dir / "test_sample.py"
    sample.write_text('TOKEN = "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ123456"\n', encoding="utf-8")

    findings = scan_repo(tmp_path)

    assert findings == []
