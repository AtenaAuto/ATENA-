import importlib
import logging

# Mantemos a importao base para que os mdulos saibam de onde herdar
from .base import BaseActuator

logger = logging.getLogger("atena.loader")

# Mapeamento dinmico baseado na estrutura atual do seu GitHub
_MODULE_MAP = {
    "Voice": ".Voice",
    "ArchitectActuator": ".architectactuator",
    "AtenaEngine": ".atena_engine",    # Novo mdulo de evoluo
    "AtenaTasks": ".atena_tasks",      # Novo gerenciador de tarefas
    "AutomationActuator": ".automtion_actuator",
    "FileActuator": ".file_actuator",
    "MeuUtil": ".meu_util",
    "NotificationActuator": ".notification_actuator",
    "ProcessActuator": ".process_actuator",
    "Services": ".services",
    "SystemActuator": ".system_actuator",
}

def __getattr__(name):
    """
    Carrega o mdulo dinamicamente apenas quando a ATENA o invoca.
    Resolve erros de carregamento em cascata.
    """
    if name in _MODULE_MAP:
        module_path = _MODULE_MAP[name]
        try:
            # Tenta importar o mdulo de forma relativa
            module = importlib.import_module(module_path, __package__)
            
            # Tenta retornar a classe com o mesmo nome (Ex: Voice no arquivo Voice.py)
            if hasattr(module, name):
                return getattr(module, name)
            return module
            
        except ImportError as e:
            logger.error(f" Erro crtico ao carregar {name}: {e}")
            raise AttributeError(f"Mdulo {name} no encontrado no caminho {module_path}")
        except Exception as e:
            logger.error(f" Falha inesperada no mdulo {name}: {e}")
            return None
            
    raise AttributeError(f"O sistema ATENA no possui o atributo: {name}")

__all__ = list(_MODULE_MAP.keys()) + ["BaseActuator"]
