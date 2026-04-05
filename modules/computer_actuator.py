#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
modules/computer_actuator.py — Atuador de Controle do Sistema para ATENA Ω
Permite que a IA execute comandos, gerencie arquivos e interaja com o sistema operacional.
"""

import os
import subprocess
import shutil
import platform
import logging
import psutil
from pathlib import Path
from typing import Dict, Any, Optional, List
from .base import BaseActuator

logger = logging.getLogger(__name__)

class ComputerActuator(BaseActuator):
    """Atuador que fornece capacidades de interação direta com o computador."""

    def _check_dependencies(self) -> None:
        """Valida dependências mínimas para operação do atuador."""
        if shutil.which("sh") is None and shutil.which("bash") is None:
            raise RuntimeError("Shell do sistema não encontrado (sh/bash).")
        # psutil já foi importado no topo; aqui validamos disponibilidade funcional.
        _ = psutil.cpu_count()

    def __init__(self):
        super().__init__()
        self.os_info = {
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
            "processor": platform.processor()
        }
        logger.info(f"[ComputerActuator] Inicializado no sistema {self.os_info['system']}")

    def execute_command(self, command: str, timeout: int = 60) -> Dict[str, Any]:
        """Executa um comando no shell do sistema e retorna a saída."""
        logger.info(f"[ComputerActuator] Executando: {command}")
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            return {
                "success": result.returncode == 0,
                "exit_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr
            }
        except subprocess.TimeoutExpired:
            logger.error(f"[ComputerActuator] Timeout ao executar: {command}")
            return {"success": False, "error": "Timeout de execução"}
        except Exception as e:
            logger.error(f"[ComputerActuator] Erro ao executar comando: {e}")
            return {"success": False, "error": str(e)}

    def list_files(self, path: str = ".") -> List[str]:
        """Lista arquivos em um diretório específico."""
        try:
            target = Path(path).resolve()
            return [str(f.name) for f in target.iterdir()]
        except Exception as e:
            logger.error(f"[ComputerActuator] Erro ao listar arquivos em {path}: {e}")
            return []

    def get_system_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas de uso de CPU, Memória e Disco."""
        return {
            "cpu_percent": psutil.cpu_percent(interval=1),
            "memory_percent": psutil.virtual_memory().percent,
            "disk_usage": psutil.disk_usage('/').percent,
            "uptime_seconds": int(psutil.boot_time())
        }

    def write_file(self, path: str, content: str) -> bool:
        """Escreve conteúdo em um arquivo."""
        try:
            target = Path(path)
            target.parent.mkdir(parents=True, exist_ok=True)
            with open(target, 'w', encoding='utf-8') as f:
                f.write(content)
            logger.info(f"[ComputerActuator] Arquivo escrito: {path}")
            return True
        except Exception as e:
            logger.error(f"[ComputerActuator] Erro ao escrever arquivo {path}: {e}")
            return False

    def read_file(self, path: str) -> Optional[str]:
        """Lê o conteúdo de um arquivo."""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            logger.error(f"[ComputerActuator] Erro ao ler arquivo {path}: {e}")
            return None

    def kill_process(self, pid: int) -> bool:
        """Encerra um processo pelo PID."""
        try:
            p = psutil.Process(pid)
            p.terminate()
            logger.info(f"[ComputerActuator] Processo {pid} encerrado.")
            return True
        except Exception as e:
            logger.error(f"[ComputerActuator] Erro ao encerrar processo {pid}: {e}")
            return False

    def get_capabilities(self) -> Dict[str, Any]:
        """Retorna as capacidades deste atuador."""
        return {
            "name": "ComputerActuator",
            "os": self.os_info["system"],
            "features": [
                "execute_command",
                "list_files",
                "read_file",
                "write_file",
                "get_system_stats",
                "kill_process"
            ]
        }

# Instância global para ser carregada pelo __init__.py
ComputerActuatorInstance = ComputerActuator()
