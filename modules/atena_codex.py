"""Módulo AtenaCodex: orquestra diagnóstico e utilidades da ATENA."""

from __future__ import annotations

import importlib
import json
import logging
import platform
import subprocess
import sys
import threading
import os
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Dict, List, Any, Optional
from pathlib import Path

# Suporte para importação resiliente
try:
    from .AtenaSysAware import AtenaSysAware
except (ImportError, ValueError):
    try:
        from AtenaSysAware import AtenaSysAware
    except ImportError:
        # Fallback para quando executado de fora do pacote
        sys.path.append(os.path.dirname(__file__))
        try:
            from AtenaSysAware import AtenaSysAware
        except ImportError:
            # Mock básico se tudo falhar
            class AtenaSysAware:
                def get_profile(self): return {"info": "SysAware não disponível"}

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

    def __init__(self, root_path: Optional[str] = None):
        self.sysaware = AtenaSysAware()
        self._lock = threading.RLock()
        # Define a raiz do projeto para comandos relativos
        if root_path:
            self.root_path = Path(root_path)
        else:
            # Assume que estamos em /modules/ e a raiz é um nível acima
            self.root_path = Path(__file__).parent.parent

    def environment_snapshot(self) -> Dict:
        """Retorna snapshot básico do host e runtime."""
        with self._lock:
            try:
                profile = dict(self.sysaware.get_profile())
            except Exception:
                profile = {"error": "Falha ao obter perfil do SysAware"}
                
            profile.update(
                {
                    "python_executable": sys.executable,
                    "platform": platform.platform(),
                    "checked_at": datetime.utcnow().isoformat() + "Z",
                    "root_path": str(self.root_path.absolute()),
                }
            )
            return profile

    def check_python_modules(self) -> Dict[str, List[Dict]]:
        """Valida módulos essenciais e opcionais de runtime."""
        essential = [asdict(self._check_single_module(name)) for name in self.ESSENTIAL_MODULES]
        optional = [asdict(self._check_single_module(name)) for name in self.OPTIONAL_MODULES]
        return {"essential": essential, "optional": optional}

    def run_local_commands(self, timeout_seconds: int = 120) -> List[Dict]:
        """Executa comandos seguros de validação local na raiz do projeto."""
        # Lista de arquivos para verificar compilação, se existirem
        targets = ["core/main.py", "core/neural_api.py", "core/neural_dashboard.py", "modules"]
        existing_targets = [t for t in targets if (self.root_path / t).exists()]
        
        commands = []
        if existing_targets:
            commands.append([sys.executable, "-m", "compileall", "-q"] + existing_targets)
        
        # Tenta importar o core.main se possível
        commands.append([sys.executable, "-c", "import sys; sys.path.append('core'); import main; print('Core Import: OK')"])
        
        out = []
        for cmd in commands:
            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=timeout_seconds,
                    check=False,
                    cwd=str(self.root_path)
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
            except Exception as e:
                out.append(
                    {
                        "command": " ".join(cmd),
                        "returncode": -2,
                        "stdout": "",
                        "stderr": str(e),
                    }
                )
        return out

    def run_full_diagnostic(self, include_commands: bool = True, timeout_seconds: int = 120) -> Dict:
        """Executa diagnóstico completo em uma chamada única."""
        snapshot = self.environment_snapshot()
        module_checks = self.check_python_modules()
        command_checks = self.run_local_commands(timeout_seconds=timeout_seconds) if include_commands else []

        essentials_ok = all(item["ok"] for item in module_checks["essential"])
        # Consideramos OK se os comandos que rodaram retornaram 0
        commands_ok = all(item["returncode"] == 0 for item in command_checks) if command_checks else True

        status = "ok" if (essentials_ok and commands_ok) else "partial"
        diagnostic = {
            "status": status,
            "snapshot": snapshot,
            "modules": module_checks,
            "commands": command_checks,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        logger.info("[AtenaCodex] diagnóstico concluído com status=%s", status)
        return diagnostic

    @staticmethod
    def _check_single_module(module_name: str) -> CheckResult:
        # Mapeamento de nomes de pacotes pip para nomes de importação
        import_map = {
            "sklearn": "sklearn",
            "dotenv": "dotenv",
            "yaml": "yaml",
            "faiss": "faiss",
            "chromadb": "chromadb"
        }
        
        actual_import = import_map.get(module_name, module_name)
        
        try:
            module = importlib.import_module(actual_import)
            version = getattr(module, "__version__", "desconhecida")
            return CheckResult(module_name, True, f"versão={version}")
        except Exception as exc:
            return CheckResult(module_name, False, str(exc))


def _main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s - %(message)s")
    # Tenta detectar a raiz do projeto se estiver rodando dentro de modules/
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    result = AtenaCodex(root_path=root).run_full_diagnostic()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
