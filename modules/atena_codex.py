"""Módulo AtenaCodex: orquestra diagnóstico e utilidades da ATENA."""

from __future__ import annotations

import importlib
import json
import logging
import platform
import subprocess
import sys
import threading
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Dict, List

from .AtenaSysAware import AtenaSysAware

logger = logging.getLogger("atena.codex")


@dataclass
class CheckResult:
    name: str
    ok: bool
    details: str


class AtenaCodex:
    """Camada utilitária de operação/diagnóstico para a ATENA."""

    ESSENTIAL_MODULES = [
        "aiosqlite",
        "aiohttp",
        "numpy",
        "pandas",
        "transformers",
        "torch",
        "chromadb",
        "faiss",
        "networkx",
    ]

    OPTIONAL_MODULES = [
        "matplotlib",
        "seaborn",
        "sklearn",
        "dotenv",
        "tqdm",
        "colorama",
        "requests",
        "yaml",
    ]

    def __init__(self):
        self.sysaware = AtenaSysAware()
        self._lock = threading.RLock()

    def environment_snapshot(self) -> Dict:
        """Retorna snapshot básico do host e runtime."""
        with self._lock:
            profile = dict(self.sysaware.get_profile())
            profile.update(
                {
                    "python_executable": sys.executable,
                    "platform": platform.platform(),
                    "checked_at": datetime.utcnow().isoformat() + "Z",
                }
            )
            return profile

    def check_python_modules(self) -> Dict[str, List[Dict]]:
        """Valida módulos essenciais e opcionais de runtime."""
        essential = [asdict(self._check_single_module(name)) for name in self.ESSENTIAL_MODULES]
        optional = [asdict(self._check_single_module(name)) for name in self.OPTIONAL_MODULES]
        return {"essential": essential, "optional": optional}

    def run_local_commands(self, timeout_seconds: int = 120) -> List[Dict]:
        """Executa comandos seguros de validação local."""
        commands = [
            [sys.executable, "-m", "compileall", "-q", "main.py", "api.py", "dashboard.py", "modules"],
            [sys.executable, "-c", "import main; print('import main: OK')"],
        ]
        out = []
        for cmd in commands:
            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=timeout_seconds,
                    check=False,
                )
                out.append(
                    {
                        "command": " ".join(cmd),
                        "returncode": result.returncode,
                        "stdout": result.stdout.strip(),
                        "stderr": result.stderr.strip(),
                    }
                )
            except subprocess.TimeoutExpired:
                out.append(
                    {
                        "command": " ".join(cmd),
                        "returncode": -1,
                        "stdout": "",
                        "stderr": f"timeout>{timeout_seconds}s",
                    }
                )
        return out

    def run_full_diagnostic(self, include_commands: bool = True, timeout_seconds: int = 120) -> Dict:
        """Executa diagnóstico completo em uma chamada única."""
        snapshot = self.environment_snapshot()
        module_checks = self.check_python_modules()
        command_checks = self.run_local_commands(timeout_seconds=timeout_seconds) if include_commands else []

        essentials_ok = all(item["ok"] for item in module_checks["essential"])
        commands_ok = all(item["returncode"] == 0 for item in command_checks) if include_commands else True

        status = "ok" if (essentials_ok and commands_ok) else "partial"
        diagnostic = {
            "status": status,
            "snapshot": snapshot,
            "modules": module_checks,
            "commands": command_checks,
        }
        logger.info("[AtenaCodex] diagnóstico concluído com status=%s", status)
        return diagnostic

    @staticmethod
    def _check_single_module(module_name: str) -> CheckResult:
        try:
            module = importlib.import_module(module_name)
            version = getattr(module, "__version__", "desconhecida")
            return CheckResult(module_name, True, f"versão={version}")
        except Exception as exc:  # pragma: no cover - diagnóstico resiliente
            return CheckResult(module_name, False, str(exc))


def _main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s - %(message)s")
    result = AtenaCodex().run_full_diagnostic()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
