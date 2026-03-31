import importlib

# Mantemos as importações base que não geram conflito
from .base import BaseActuator

# Dicionário de mapeamento para carregamento dinâmico (Lazy Loading)
# Atualizado com os novos módulos da print: Voice, atena_tasks e services
_MODULE_MAP = {
    "FileActuator": ".file_actuator",
    "ProcessActuator": ".process_actuator",
    "NotificationActuator": ".notification_actuator",
    "AutomationActuator": ".automation_actuator",
    "SystemActuator": ".system_actuator",
    "ArchitectActuator": ".architect_actuator",
    "Voice": ".Voice",            # Novo: O sistema de fala
    "AtenaTasks": ".atena_tasks", # Novo: O cérebro de tarefas
    "Services": ".services",      # Novo: O maestro das habilidades
}

def __getattr__(name):
    """
    Carrega o módulo dinamicamente apenas quando acessado.
    """
    if name in _MODULE_MAP:
        module_path = _MODULE_MAP[name]
        try:
            # Importa o submódulo relativamente
            module = importlib.import_module(module_path, __package__)
            return getattr(module, name)
        except (ImportError, AttributeError) as e:
            # Se o arquivo existir mas a classe/função interna tiver nome diferente
            # ex: atena_tasks.py pode conter a classe 'TaskManager'
            module = importlib.import_module(module_path, __package__)
            return module 
            
    raise AttributeError(f"module {__name__} has no attribute {name}")

__all__ = list(_MODULE_MAP.keys()) + ["BaseActuator"]
