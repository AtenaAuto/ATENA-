#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Catálogo interno de skills/plugins com curadoria."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class SkillRecord:
    skill_id: str
    version: str
    risk_level: str
    cost_class: str
    compatible_with: str
    approved: bool = False


class SkillMarketplace:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _load(self) -> list[dict]:
        if not self.path.exists():
            return []
        return json.loads(self.path.read_text(encoding="utf-8"))

    def _save(self, records: list[dict]) -> None:
        self.path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")

    def register(self, record: SkillRecord) -> None:
        records = self._load()
        records = [r for r in records if r.get("skill_id") != record.skill_id]
        records.append(asdict(record))
        self._save(records)

    def approve(self, skill_id: str) -> bool:
        records = self._load()
        updated = False
        for r in records:
            if r.get("skill_id") == skill_id:
                r["approved"] = True
                updated = True
        if updated:
            self._save(records)
        return updated

    def list_records(self) -> list[dict]:
        return self._load()
