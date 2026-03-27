#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Módulo de Consciência do Host para Atena Ω
Permite que a Atena conheça e se adapte ao computador onde roda.
"""

import datetime
import logging
import multiprocessing
import os
import platform
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional, Tuple

import psutil

# Dependências opcionais
try:
    import torch
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False

logger = logging.getLogger("atena.sysaware")

# =============================================================
# 1. Perfil do host
# =============================================================

@dataclass
class HostProfile:
    """Perfil completo do computador onde a Atena está rodando."""
    os_name: str
    os_version: str
    machine: str
    cpu_count: int
    cpu_freq_mhz: float
    total_ram_gb: float
    available_ram_gb: float
    has_gpu: bool = False
    gpu_name: Optional[str] = None
    is_ci: bool = False
    is_container: bool = False
    is_github_actions: bool = False
    python_version: str = sys.version
    installed_packages: Optional[Dict[str, str]] = None  # lazy load
    disk_free_gb: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.datetime.now().isoformat())

# =============================================================
# 2. Módulo principal
# =============================================================

class AtenaSysAware:
    """Dá 'consciência do host' para a Atena."""

    def __init__(self):
        self.profile: HostProfile = self._scan_host()
        self._last_monitor: Dict = {}
        self._cache: Dict = {}
        logger.info(f"[SysAware] Host detectado: {self.profile.os_name} {self.profile.machine} "
                    f"| CPU: {self.profile.cpu_count} cores | RAM: {self.profile.total_ram_gb:.1f} GB "
                    f"| GPU: {'Sim' if self.profile.has_gpu else 'Não'}")

    # ---------------------------------------------------------
    # 3. Escaneamento inicial
    # ---------------------------------------------------------
    def _scan_host(self) -> HostProfile:
        """Escaneia o ambiente uma vez no init."""
        p = psutil.virtual_memory()
        cpu_freq = psutil.cpu_freq()
        disk = psutil.disk_usage("/")

        # GPU detection
        has_gpu = False
        gpu_name = None
        if HAS_TORCH and torch.cuda.is_available():
            has_gpu = True
            gpu_name = torch.cuda.get_device_name(0)
        elif HAS_TORCH and hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            has_gpu = True
            gpu_name = "Apple Silicon MPS"

        # Container detection
        is_container = Path("/.dockerenv").exists() or "docker" in os.getenv("HOSTNAME", "")
        is_github_actions = os.getenv("GITHUB_ACTIONS", "false").lower() == "true"

        profile = HostProfile(
            os_name=platform.system(),
            os_version=platform.release(),
            machine=platform.machine(),
            cpu_count=multiprocessing.cpu_count(),
            cpu_freq_mhz=cpu_freq.current if cpu_freq else 0.0,
            total_ram_gb=p.total / (1024**3),
            available_ram_gb=p.available / (1024**3),
            has_gpu=has_gpu,
            gpu_name=gpu_name,
            is_ci=is_github_actions,
            is_container=is_container,
            is_github_actions=is_github_actions,
            disk_free_gb=disk.free / (1024**3),
            timestamp=datetime.datetime.now().isoformat()
        )
        return profile

    # ---------------------------------------------------------
    # 4. Métodos de consulta do perfil
    # ---------------------------------------------------------
    def get_profile(self) -> Dict:
        """Retorna o perfil como dict para fácil uso."""
        return self.profile.__dict__

    def get_installed_packages(self) -> Dict[str, str]:
        """Retorna dicionário de pacotes instalados (lazy load)."""
        if self.profile.installed_packages is None:
            try:
                import pkg_resources
                self.profile.installed_packages = {
                    dist.project_name: dist.version for dist in pkg_resources.working_set
                }
            except ImportError:
                self.profile.installed_packages = {}
        return self.profile.installed_packages

    def can_use_gpu(self) -> bool:
        return self.profile.has_gpu

    def has_enough_ram(self, min_gb: float = 2.0) -> bool:
        return self.profile.available_ram_gb >= min_gb

    def is_low_resource(self) -> bool:
        """Detecta se máquina é fraca (ex: CI gratuito, notebook antigo)."""
        return (self.profile.cpu_count <= 2 or
                self.profile.total_ram_gb <= 4 or
                self.profile.is_ci)

    # ---------------------------------------------------------
    # 5. Monitoramento em tempo real
    # ---------------------------------------------------------
    def monitor_resources(self) -> Dict:
        """Retorna uso atual de recursos (pode ser chamado por ciclo)."""
        cpu = psutil.cpu_percent(interval=0.1)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        self._last_monitor = {
            "cpu_percent": cpu,
            "memory_used_gb": mem.used / (1024**3),
            "memory_percent": mem.percent,
            "disk_free_gb": disk.free / (1024**3),
            "disk_percent": disk.percent,
            "timestamp": datetime.datetime.now().isoformat()
        }
        return self._last_monitor

    def is_safe_to_evolve_deep(self) -> bool:
        """Decide se pode ativar deep self-mod com segurança."""
        if not self.profile.has_gpu:
            # Em CPU, mais conservador
            res = self.monitor_resources()
            return (res["cpu_percent"] < 60 and
                    res["memory_percent"] < 75 and
                    self.profile.available_ram_gb > 1.5)
        else:
            # Com GPU, pode ser mais ousado
            res = self.monitor_resources()
            return (res["cpu_percent"] < 80 and
                    res["memory_percent"] < 85 and
                    self.profile.available_ram_gb > 1.0)

    # ---------------------------------------------------------
    # 6. Sugestões de ajustes dinâmicos
    # ---------------------------------------------------------
    def suggest_mutation_adjustments(self) -> Tuple[Dict[str, float], Dict[str, float]]:
        """
        Retorna dois dicionários:
        - config_adjust: fatores para modificar constantes de Config (ex: CANDIDATES_PER_CYCLE)
        - weight_adjust: fatores para ajustar pesos de tipos de mutação.
        """
        config_adjust = {}
        weight_adjust = {}

        # Modo low‑resource
        if self.is_low_resource():
            config_adjust["CANDIDATES_PER_CYCLE"] = 0.5
            config_adjust["RECURSIVE_CYCLES"] = 1
            weight_adjust["add_numba_jit"] = 0.2
            weight_adjust["parallelize_loop"] = 0.1
            weight_adjust["grok_generate"] = 1.5          # prefere Grok, menos CPU local

        # GPU disponível
        if self.profile.has_gpu:
            weight_adjust["add_numba_jit"] = weight_adjust.get("add_numba_jit", 1.0) * 2.0
            weight_adjust["vectorize_loop"] = weight_adjust.get("vectorize_loop", 1.0) * 1.8
            # Em GPU, pode usar mais workers
            config_adjust["PARALLEL_WORKERS"] = config_adjust.get("PARALLEL_WORKERS", 1.0) * 1.5

        # CI (GitHub Actions)
        if self.profile.is_ci:
            config_adjust["CANDIDATES_PER_CYCLE"] = min(config_adjust.get("CANDIDATES_PER_CYCLE", 1.0), 0.6)
            config_adjust["RECURSIVE_CYCLES"] = 1
            weight_adjust["add_numba_jit"] = weight_adjust.get("add_numba_jit", 1.0) * 0.3
            weight_adjust["parallelize_loop"] = 0.0
            weight_adjust["grok_generate"] = weight_adjust.get("grok_generate", 1.0) * 1.2

        # Ajustes de tempo de execução baseado no uso atual
        res = self.monitor_resources()
        if res["cpu_percent"] > 80:
            config_adjust["PARALLEL_WORKERS"] = min(config_adjust.get("PARALLEL_WORKERS", 1.0), 0.5)
        if res["memory_percent"] > 85:
            config_adjust["CANDIDATES_PER_CYCLE"] = min(config_adjust.get("CANDIDATES_PER_CYCLE", 1.0), 0.7)

        return config_adjust, weight_adjust
