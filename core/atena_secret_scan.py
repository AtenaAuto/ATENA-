#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Scanner de segredos para hardening de segurança da ATENA."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

DEFAULT_EXCLUDES = {".git", ".venv", "venv", "__pycache__", ".pytest_cache", "node_modules"}
TEXT_EXTENSIONS = {
    ".py",
    ".md",
    ".txt",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".ini",
    ".cfg",
    ".env",
    ".sh",
}

SECRET_PATTERNS = [
    ("github_classic", re.compile(r"\bghp_[A-Za-z0-9]{20,}\b")),
    ("github_pat", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b")),
    ("openai_key", re.compile(r"\bsk-[A-Za-z0-9]{20,}\b")),
    ("aws_access_key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
]


def _iter_candidate_files(root: Path, include_tests: bool = False) -> list[Path]:
    files: list[Path] = []
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if any(part in DEFAULT_EXCLUDES for part in p.parts):
            continue
        if not include_tests and ("tests" in p.parts or p.name.startswith("test_")):
            continue
        if p.suffix.lower() not in TEXT_EXTENSIONS and p.name not in {".env", ".env.example"}:
            continue
        files.append(p)
    return files


def scan_repo(root: Path, include_tests: bool = False) -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    for file_path in _iter_candidate_files(root, include_tests=include_tests):
        try:
            lines = file_path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            continue
        for idx, line in enumerate(lines, start=1):
            for label, pattern in SECRET_PATTERNS:
                if pattern.search(line):
                    findings.append(
                        {
                            "file": str(file_path.relative_to(root)),
                            "line": idx,
                            "pattern": label,
                        }
                    )
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description="Escaneia repositório em busca de segredos.")
    parser.add_argument("--root", default=".", help="Diretório raiz para escanear")
    parser.add_argument("--include-tests", action="store_true", help="Inclui arquivos de teste no scan")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    findings = scan_repo(root, include_tests=args.include_tests)
    if not findings:
        print("✅ Secret scan: nenhum vazamento detectado.")
        return 0

    print(f"❌ Secret scan: {len(findings)} possível(is) vazamento(s) detectado(s).")
    for item in findings[:100]:
        print(f"- {item['file']}:{item['line']} [{item['pattern']}]")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
