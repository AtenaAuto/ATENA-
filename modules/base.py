import logging
import time
import functools
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, Callable
from datetime import datetime

logger = logging.getLogger("atena.actuators")

def log_action(action_name: Optional[str] = None):
    """
    Decorator para registrar automaticamente a execução de métodos da classe BaseActuator.
    Registra o nome da ação, parâmetros, tempo de execução e exceções.
    """
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
    Classe base abstrata para todos os atuadores do sistema Atena.
    
    Fornece funcionalidades comuns:
        - Verificação de dependências (abstrato)
        - Logging estruturado com contexto
        - Rastreamento de ações (tempo, sucesso/erro)
        - Configuração opcional de sysaware
    
    Atributos:
        sysaware: Instância de SysAware (para acesso a contexto do sistema, opcional)
        history: Lista opcional para armazenar histórico de ações (se ativado)
    """
    
    def __init__(self, sysaware: Optional[Any] = None, enable_history: bool = False):
        """
        Inicializa o atuador.

        Args:
            sysaware: Instância de SysAware (fornece contexto adicional, ex: sistema operacional, configurações)
            enable_history: Se True, mantém um histórico interno das ações executadas.
        """
        self.sysaware = sysaware
        self.enable_history = enable_history
        self._action_history: list = [] if enable_history else None
        self._check_dependencies()
        logger.debug(f"{self.__class__.__name__} inicializado com sysaware={sysaware is not None}")

    @abstractmethod
    def _check_dependencies(self) -> None:
        """
        Verifica se as dependências necessárias para o atuador estão disponíveis.
        
        Deve ser implementado por cada subclasse.
        Exemplo: verificar se bibliotecas (psutil, pyautogui) ou comandos (pactl) estão presentes.
        
        Raises:
            ImportError: Se alguma biblioteca obrigatória não estiver instalada.
            RuntimeError: Se alguma ferramenta de sistema não for encontrada.
        """
        pass

    def log_action(self, action: str, details: Optional[Dict[str, Any]] = None, level: int = logging.INFO) -> None:
        """
        Registra uma ação realizada pelo atuador com contexto estruturado.
        
        Args:
            action: Nome da ação (ex: "click", "set_volume", "kill_process").
            details: Dicionário com detalhes adicionais (parâmetros, resultados, etc.).
            level: Nível de log (logging.INFO, WARNING, ERROR, etc.).
        """
        msg = f"[{self.__class__.__name__}] {action}"
        if details:
            # Evita expor dados sensíveis como comandos completos, senhas, etc.
            safe_details = self._sanitize_details(details)
            msg += f" {safe_details}"
        
        logger.log(level, msg)
        
        # Se histórico estiver ativado, armazena a ação
        if self.enable_history and self._action_history is not None:
            self._action_history.append({
                "timestamp": datetime.now().isoformat(),
                "actuator": self.__class__.__name__,
                "action": action,
                "details": details,
                "level": logging.getLevelName(level)
            })
            # Limita histórico a 1000 itens para evitar vazamento de memória
            if len(self._action_history) > 1000:
                self._action_history.pop(0)

    def _sanitize_details(self, details: Dict[str, Any]) -> Dict[str, Any]:
        """
        Remove ou mascara informações sensíveis dos detalhes antes de logar.
        
        Pode ser sobrescrito por subclasses para regras específicas.
        """
        sensitive_keys = {"password", "token", "secret", "command"}  # command pode conter senhas
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
        """
        Retorna o histórico de ações (se enable_history=True).
        
        Args:
            limit: Número máximo de ações retornadas (mais recentes).
        
        Returns:
            Lista de dicionários com as ações registradas.
        """
        if not self.enable_history:
            logger.warning(f"{self.__class__.__name__}: histórico não está habilitado.")
            return []
        if limit:
            return self._action_history[-limit:]
        return self._action_history.copy()

    def log_error(self, action: str, error: Exception, details: Optional[Dict] = None) -> None:
        """
        Registra um erro ocorrido durante uma ação, com detalhes da exceção.
        """
        error_details = {
            "error_type": type(error).__name__,
            "error_msg": str(error)
        }
        if details:
            error_details.update(details)
        self.log_action(action, error_details, level=logging.ERROR)

    @log_action()  # decorator para registrar a própria chamada de execute (se usado)
    def execute(self, action: str, **kwargs) -> Any:
        """
        Método genérico para executar uma ação no atuador.
        
        Por padrão, levanta NotImplementedError. Subclasses podem implementar
        um dispatcher para ações comuns.
        
        Args:
            action: Nome da ação a executar.
            **kwargs: Parâmetros específicos da ação.
        
        Returns:
            Resultado da ação.
        """
        raise NotImplementedError(f"{self.__class__.__name__} não implementa o método execute() genérico.")

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(sysaware={self.sysaware is not None}, history={self.enable_history})"
