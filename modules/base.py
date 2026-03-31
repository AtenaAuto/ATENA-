import logging
import time
import functools
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, Callable
from datetime import datetime

# Configuração do Logger para os Atuadores
logger = logging.getLogger("atena.actuators")

def track_action(action_name: Optional[str] = None):
    """
    DECORADOR CORRIGIDO: Renomeado para 'track_action' para evitar conflito 
    com o método 'log_action' da classe BaseActuator.
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            act_name = action_name or func.__name__
            start = time.time()
            try:
                result = func(self, *args, **kwargs)
                duration = time.time() - start
                # Chama o método da instância corretamente
                self.log_action(act_name, {
                    "args": args,
                    "kwargs": kwargs,
                    "duration_ms": round(duration * 1000, 2),
                    "status": "success"
                })
                return result
            except Exception as e:
                duration = time.time() - start
                self.log_action(act_name, {
                    "args": args,
                    "kwargs": kwargs,
                    "duration_ms": round(duration * 1000, 2),
                    "status": "error",
                    "error": str(e)
                }, level=logging.ERROR)
                raise
        return wrapper
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            act_name = action_name or func.__name__
            start = time.time()
            try:
                result = func(self, *args, **kwargs)
                duration = time.time() - start
                self.log_action(act_name, {
                    "args": args,
                    "kwargs": kwargs,
                    "duration_ms": round(duration * 1000, 2),
                    "status": "success"
                })
                return result
            except Exception as e:
                duration = time.time() - start
                self.log_action(act_name, {
                    "args": args,
                    "kwargs": kwargs,
                    "duration_ms": round(duration * 1000, 2),
                    "status": "error",
                    "error": str(e)
                }, level=logging.ERROR)
                raise
        return wrapper
    return decorator

class BaseActuator(ABC):
    """
    Classe base abstrata para todos os atuadores da ATENA Ω.
    """
    
    def __init__(self, sysaware: Optional[Any] = None, enable_history: bool = False):
        self.sysaware = sysaware
        self.enable_history = enable_history
        self._action_history: list = [] if enable_history else None
        self._check_dependencies()
        logger.debug(f"{self.__class__.__name__} inicializado com sysaware={sysaware is not None}")

    @abstractmethod
    def _check_dependencies(self) -> None:
        """Verifica dependências (ex: bibliotecas ou comandos de voz)."""
        pass

    def log_action(self, action: str, details: Optional[Dict[str, Any]] = None, level: int = logging.INFO) -> None:
        """Registra a ação no terminal da ATENA."""
        msg = f"[{self.__class__.__name__}] {action}"
        if details:
            safe_details = self._sanitize_details(details)
            msg += f" {safe_details}"
        
        logger.log(level, msg)
        
        if self.enable_history and self._action_history is not None:
            self._action_history.append({
                "timestamp": datetime.now().isoformat(),
                "actuator": self.__class__.__name__,
                "action": action,
                "details": details,
                "level": logging.getLevelName(level)
            })
            if len(self._action_history) > 1000:
                self._action_history.pop(0)

    def _sanitize_details(self, details: Dict[str, Any]) -> Dict[str, Any]:
        """Remove dados sensíveis como senhas ou tokens do log."""
        sensitive_keys = {"password", "token", "secret", "command"}
        safe = {}
        for k, v in details.items():
            if k in sensitive_keys:
                safe[k] = "***REDACTED***"
            elif isinstance(v, dict):
                safe[k] = self._sanitize_details(v)
            else:
                safe[k] = v
        return safe

    def get_action_history(self, limit: Optional[int] = None) -> list:
        if not self.enable_history:
            return []
        if limit:
            return self._action_history[-limit:]
        return self._action_history.copy()

    def log_error(self, action: str, error: Exception, details: Optional[Dict] = None) -> None:
        error_details = {"error_type": type(error).__name__, "error_msg": str(error)}
        if details:
            error_details.update(details)
        self.log_action(action, error_details, level=logging.ERROR)

    @track_action() # Uso do novo nome do decorador
    def execute(self, action: str, **kwargs) -> Any:
        raise NotImplementedError(f"{self.__class__.__name__} não implementa execute().")

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(sysaware={self.sysaware is not None}, history={self.enable_history})"
