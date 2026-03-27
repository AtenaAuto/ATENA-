import importlib

# Mantemos as importações base que não geram conflito
from .base import BaseActuator

# Dicionário de mapeamento para carregamento dinâmico (Lazy Loading)
_MODULE_MAP = {
    "FileActuator": ".file_actuator",
    "ProcessActuator": ".process_actuator",
    "NotificationActuator": ".notification_actuator",
    "AutomationActuator": ".automation_actuator",
    "SystemActuator": ".system_actuator",
    "KnowledgeMiner": ".knowledge_miner",
    "ArchitectActuator": ".architect_actuator", # Certifique-se que o nome do arquivo é este
}

def __getattr__(name):
    """
    Esta função mágica do Python 3.7+ carrega o módulo 
    apenas quando alguém tenta acessá-lo.
    """
    if name in _MODULE_MAP:
        module_path = _MODULE_MAP[name]
        # Importa o submódulo relativamente
        module = importlib.import_module(module_path, __package__)
        return getattr(module, name)
    raise AttributeError(f"module {__name__} has no attribute {name}")

__all__ = list(_MODULE_MAP.keys()) + ["BaseActuator"]
