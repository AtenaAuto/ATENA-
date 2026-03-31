import importlib
import logging

# Mantemos a importação base para que os módulos saibam de onde herdar
from .base import BaseActuator

logger = logging.getLogger("atena.loader")

# Mapeamento dinâmico baseado na estrutura atual do seu GitHub
_MODULE_MAP = {
    "Voice": ".Voice",
    "ArchitectActuator": ".architectactuator",
    "AtenaEngine": ".atena_engine",    # Novo módulo de evolução
    "AtenaTasks": ".atena_tasks",      # Novo gerenciador de tarefas
    "AutomationActuator": ".automátion_actuator",
    "FileActuator": ".file_actuator",
    "MeuUtil": ".meu_util",
    "NotificationActuator": ".notification_actuator",
    "ProcessActuator": ".process_actuator",
    "Services": ".services",
    "SystemActuator": ".system_actuator",
}

def __getattr__(name):
    """
    Carrega o módulo dinamicamente apenas quando a ATENA o invoca.
    Resolve erros de carregamento em cascata.
    """
    if name in _MODULE_MAP:
        module_path = _MODULE_MAP[name]
        try:
            # Tenta importar o módulo de forma relativa
            module = importlib.import_module(module_path, __package__)
            
            # Tenta retornar a classe com o mesmo nome (Ex: Voice no arquivo Voice.py)
            if hasattr(module, name):
                return getattr(module, name)
            return module
            
        except ImportError as e:
            logger.error(f"❌ Erro crítico ao carregar {name}: {e}")
            raise AttributeError(f"Módulo {name} não encontrado no caminho {module_path}")
        except Exception as e:
            logger.error(f"⚠️ Falha inesperada no módulo {name}: {e}")
            return None
            
    raise AttributeError(f"O sistema ATENA não possui o atributo: {name}")

__all__ = list(_MODULE_MAP.keys()) + ["BaseActuator"]
