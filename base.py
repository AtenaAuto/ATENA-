import logging
from abc import ABC, abstractmethod

logger = logging.getLogger("atena.actuators")

class BaseActuator(ABC):
    """Classe base para todos os atuadores."""
    def __init__(self, sysaware=None):
        self.sysaware = sysaware
        self._check_dependencies()

    @abstractmethod
    def _check_dependencies(self):
        """Verifica se as dependências necessárias estão disponíveis."""
        pass

    def log_action(self, action: str, details: dict = None):
        """Registra uma ação realizada."""
        logger.info(f"[{self.__class__.__name__}] {action}" + (f" {details}" if details else ""))
