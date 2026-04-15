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
    SAFE_COMMAND_PREFIXES = (
        "echo",
        "pwd",
        "ls",
        "cat",
        "head",
        "tail",
        "wc",
        "python3 -c",
    )

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

    def is_command_allowed(self, command: str) -> bool:
        """Valida se o comando está em uma allowlist segura para uso conversacional."""
        normalized = command.strip()
        if not normalized:
            return False
        return any(
            normalized == prefix or normalized.startswith(prefix + " ")
            for prefix in self.SAFE_COMMAND_PREFIXES
        )

    def execute_safe_command(self, command: str, timeout: int = 30) -> Dict[str, Any]:
        """
        Executa comando apenas se estiver na allowlist.
        Esse método é recomendado para modo conversacional com humanos.
        """
        if not self.is_command_allowed(command):
            return {
                "success": False,
                "error": "Comando bloqueado pela política de segurança do ComputerActuator.",
                "command": command,
            }
        return self.execute_command(command=command, timeout=timeout)

    def run_task_sequence(self, tasks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Executa uma sequência de tarefas estruturadas para uso em diálogo.
        Suporta ações: execute_safe_command, list_files, read_file, write_file, get_system_stats.
        """
        results: List[Dict[str, Any]] = []
        for index, task in enumerate(tasks, start=1):
            action = task.get("action")
            payload = task.get("payload", {})
            item_result: Dict[str, Any] = {"step": index, "action": action, "ok": True}

            try:
                if action == "execute_safe_command":
                    command = str(payload.get("command", ""))
                    timeout = int(payload.get("timeout", 30))
                    exec_result = self.execute_safe_command(command=command, timeout=timeout)
                    item_result["result"] = exec_result
                    item_result["ok"] = bool(exec_result.get("success"))
                elif action == "list_files":
                    path = str(payload.get("path", "."))
                    item_result["result"] = self.list_files(path=path)
                elif action == "read_file":
                    path = str(payload.get("path", ""))
                    item_result["result"] = self.read_file(path=path)
                    item_result["ok"] = item_result["result"] is not None
                elif action == "write_file":
                    path = str(payload.get("path", ""))
                    content = str(payload.get("content", ""))
                    item_result["result"] = self.write_file(path=path, content=content)
                    item_result["ok"] = bool(item_result["result"])
                elif action == "get_system_stats":
                    item_result["result"] = self.get_system_stats()
                else:
                    item_result["ok"] = False
                    item_result["error"] = f"Ação não suportada: {action}"
            except Exception as exc:
                item_result["ok"] = False
                item_result["error"] = str(exc)

            results.append(item_result)

        success_count = sum(1 for r in results if r.get("ok"))
        return {
            "total_steps": len(results),
            "successful_steps": success_count,
            "failed_steps": len(results) - success_count,
            "results": results,
        }

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
                "execute_safe_command",
                "list_files",
                "read_file",
                "write_file",
                "get_system_stats",
                "kill_process",
                "run_task_sequence",
            ]
        }

# Instância global para ser carregada pelo __init__.py
ComputerActuatorInstance = ComputerActuator()
