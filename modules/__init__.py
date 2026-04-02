"""
Carregador dinâmico de atuadores da Atena.
Suporta carregamento sob demanda, mas também pode carregar todos antecipadamente.
"""

import importlib
import logging
from typing import Dict, Any, Optional

from .base import BaseActuator

logger = logging.getLogger(__name__)

# Cache de módulos já carregados
_loaded_modules: Dict[str, Any] = {}

# Registro explícito dos caminhos dos módulos
_REGISTRY: Dict[str, str] = {
    "Voice": ".Voice",
    "ArchitectActuator": ".architectactuator",
    "AtenaEngine": ".atena_engine",
    "AtenaTasks": ".atena_tasks",
    "AutomationActuator": ".automation_actuator",
    "FileActuator": ".file_actuator",
    "MeuUtil": ".meu_util",
    "NotificationActuator": ".notification_actuator",
    "ProcessActuator": ".process_actuator",
    "Services": ".services",
    "SystemActuator": ".system_actuator",
}

def _load_module(name: str) -> Any:
    """Carrega um único módulo e armazena em cache."""
    module_path = _REGISTRY[name]
    try:
        module = importlib.import_module(module_path, package=__package__)
        if hasattr(module, name):
            obj = getattr(module, name)
        else:
            logger.warning(f"Módulo {module_path} não contém classe {name}, retornando módulo")
            obj = module
        _loaded_modules[name] = obj
        logger.debug(f"Módulo carregado: {name}")
        return obj
    except ImportError as e:
        logger.error(f"Erro ao carregar módulo {name} de {module_path}: {e}")
        raise
    except Exception as e:
        logger.error(f"Erro inesperado ao carregar {name}: {e}")
        raise

def load_all() -> None:
    """Carrega todos os módulos registrados antecipadamente."""
    for name in _REGISTRY:
        _load_module(name)
    logger.info(f"Todos os {len(_REGISTRY)} módulos carregados com sucesso.")

def __getattr__(name: str) -> Any:
    """Carrega sob demanda se ainda não carregado."""
    if name in _loaded_modules:
        return _loaded_modules[name]
    if name in _REGISTRY:
        return _load_module(name)
    raise AttributeError(f"'{__name__}' não possui o atributo '{name}'")

def __dir__() -> list:
    return sorted(list(_REGISTRY.keys()) + ["BaseActuator", "load_all"])

# Opcional: carregar todos imediatamente (descomente se quiser comportamento antigo)
# load_all()

__all__ = list(_REGISTRY.keys()) + ["BaseActuator", "load_all"]
