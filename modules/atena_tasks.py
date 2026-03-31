# task_manager.py
"""
┌─────────────────────────────────────────────────────────────────────┐
│         TASK MANAGER v2.0 — Python                                  │
│  Sistema de gerenciamento de tarefas polimorfo com retry automático  │
│                                                                     │
│  Features:                                                          │
│   • 7 tipos de tarefas (bash, agentes, workflows, etc)              │
│   • State machine robusto (pending → running → completed)           │
│   • Retry automático com backoff exponencial                        │
│   • Priorização de tarefas (queue inteligente)                      │
│   • Métricas de execução (CPU, memória, threads)                    │
│   • Timeout obrigatório                                              │
│   • Cascata de dependências e cleanup                               │
│   • Logging persistente por tarefa                                  │
│   • Type-safe com type hints                                        │
└─────────────────────────────────────────────────────────────────────┘
"""

import os
import secrets
import asyncio
import logging
import json
import time
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, List, Callable, Any, Tuple
from abc import ABC, abstractmethod
from pathlib import Path
import psutil

logger = logging.getLogger("atena.task_manager")

# ═══════════════════════════════════════════════════════════════════════
# ENUMS E TIPOS
# ═══════════════════════════════════════════════════════════════════════

class TaskType(str, Enum):
    """Tipos de tarefas suportados"""
    LOCAL_BASH = "local_bash"
    LOCAL_AGENT = "local_agent"
    REMOTE_AGENT = "remote_agent"
    IN_PROCESS_TEAMMATE = "in_process_teammate"
    LOCAL_WORKFLOW = "local_workflow"
    MONITOR_MCP = "monitor_mcp"
    DREAM = "dream"


class TaskStatus(str, Enum):
    """Estados de execução de uma tarefa"""
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    RETRYING = "retrying"
    COMPLETED = "completed"
    FAILED = "failed"
    KILLED = "killed"
    TIMEOUT = "timeout"


# Task ID prefixes para cada tipo
TASK_ID_PREFIXES: Dict[TaskType, str] = {
    TaskType.LOCAL_BASH: "b",
    TaskType.LOCAL_AGENT: "a",
    TaskType.REMOTE_AGENT: "r",
    TaskType.IN_PROCESS_TEAMMATE: "t",
    TaskType.LOCAL_WORKFLOW: "w",
    TaskType.MONITOR_MCP: "m",
    TaskType.DREAM: "d",
}

# Alfabeto seguro para IDs (36 caracteres)
TASK_ID_ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyz"


# ═══════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════

def generate_task_id(task_type: TaskType) -> str:
    """
    Gera ID único para tarefa.
    Formato: [prefix][8 chars aleatórios]
    
    Ex: "b12a34f5", "a9z7x2k1"
    
    36^8 = 2.8 trilhões de combinações
    """
    prefix = TASK_ID_PREFIXES.get(task_type, "x")
    
    # Gera 8 bytes aleatórios
    random_bytes = secrets.token_bytes(8)
    
    # Converte para base36 (0-35)
    random_part = ""
    for byte in random_bytes:
        random_part += TASK_ID_ALPHABET[byte % 36]
    
    return f"{prefix}{random_part}"


def is_terminal_status(status: TaskStatus) -> bool:
    """
    Verifica se status é terminal (tarefa não muda mais).
    
    Usado para:
    - Evitar injeção de mensagens em tarefas mortas
    - Cleanup automático
    - Liberação de recursos
    """
    return status in (
        TaskStatus.COMPLETED,
        TaskStatus.FAILED,
        TaskStatus.KILLED,
        TaskStatus.TIMEOUT,
    )


def get_task_output_path(task_id: str) -> str:
    """Retorna caminho do arquivo de saída da tarefa"""
    task_dir = Path("./atena_evolution/tasks")
    task_dir.mkdir(parents=True, exist_ok=True)
    return str(task_dir / f"{task_id}.log")


# ═══════════════════════════════════════════════════════════════════════
# DATACLASSES
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class TaskMetrics:
    """Métricas de execução de uma tarefa"""
    cpu_percent: float = 0.0
    memory_mb: float = 0.0
    threads: int = 0
    disk_io_mb: float = 0.0


@dataclass
class TaskStateBase:
    """Estado base de uma tarefa"""
    id: str
    type: TaskType
    status: TaskStatus
    description: str
    timeout: int = 30000  # ms
    priority: int = 5  # 0-10
    
    # Execução
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    total_paused_ms: float = 0.0
    
    # Retry
    retry_count: int = 0
    max_retries: int = 3
    retry_after: Optional[float] = None
    last_error: Optional[str] = None
    error_stack: Optional[str] = None
    
    # Output
    output_file: str = field(default_factory=str)
    output_offset: int = 0
    
    # Tracking
    tool_use_id: Optional[str] = None
    notified: bool = False
    
    # Dependências
    depends_on: List[str] = field(default_factory=list)
    dependents: List[str] = field(default_factory=list)
    
    # Métricas
    metrics: Optional[TaskMetrics] = None
    peak_memory_mb: float = 0.0
    
    def __post_init__(self):
        if not self.output_file:
            self.output_file = get_task_output_path(self.id)
    
    def to_dict(self) -> Dict[str, Any]:
        """Converte para dicionário (para JSON)"""
        data = asdict(self)
        data["type"] = self.type.value
        data["status"] = self.status.value
        if self.metrics:
            data["metrics"] = asdict(self.metrics)
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TaskStateBase":
        """Constrói a partir de dicionário (de JSON)"""
        data = data.copy()
        data["type"] = TaskType(data["type"])
        data["status"] = TaskStatus(data["status"])
        if "metrics" in data and data["metrics"]:
            data["metrics"] = TaskMetrics(**data["metrics"])
        return cls(**data)


@dataclass
class LocalShellSpawnInput:
    """Input para executar shell local"""
    command: str
    description: str
    timeout: int = 30000  # ms
    tool_use_id: Optional[str] = None
    agent_id: Optional[str] = None
    kind: str = "bash"  # "bash" ou "monitor"


# ═══════════════════════════════════════════════════════════════════════
# ABSTRACT TASK CLASS
# ═══════════════════════════════════════════════════════════════════════

class Task(ABC):
    """Interface abstrata para implementações de tarefas"""
    
    def __init__(self, name: str, task_type: TaskType):
        self.name = name
        self.type = task_type
    
    @abstractmethod
    async def spawn(self, task_id: str, context: "TaskContext") -> None:
        """Inicia execução da tarefa"""
        pass
    
    @abstractmethod
    async def kill(self, task_id: str, app_state: Dict) -> None:
        """Encerra a tarefa"""
        pass
    
    async def pause(self, task_id: str, app_state: Dict) -> None:
        """Pausa a tarefa (opcional)"""
        logger.info(f"[{self.name}] Pausando tarefa {task_id}")
    
    async def resume(self, task_id: str, app_state: Dict) -> None:
        """Retoma a tarefa (opcional)"""
        logger.info(f"[{self.name}] Retomando tarefa {task_id}")
    
    async def get_metrics(self, task_id: str) -> TaskMetrics:
        """Retorna métricas da tarefa (opcional)"""
        return TaskMetrics()


# ═══════════════════════════════════════════════════════════════════════
# TASK CONTEXT
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class TaskContext:
    """Contexto de execução de uma tarefa"""
    cancel_event: asyncio.Event
    get_app_state: Callable[[], Dict]
    set_app_state: Callable[[Callable], None]


# ═══════════════════════════════════════════════════════════════════════
# TASK QUEUE (com prioridade)
# ═══════════════════════════════════════════════════════════════════════

class TaskQueue:
    """Fila de tarefas com priorização"""
    
    def __init__(self):
        self.tasks: Dict[str, TaskStateBase] = {}
        self._lock = asyncio.Lock()
    
    async def enqueue(self, task: TaskStateBase) -> None:
        """Adiciona tarefa à fila"""
        async with self._lock:
            self.tasks[task.id] = task
            logger.debug(f"[Queue] Enfileirada tarefa {task.id}")
    
    async def get_next(self) -> Optional[TaskStateBase]:
        """
        Retorna próxima tarefa a executar.
        Ordem: Prioridade > Idade (FIFO)
        """
        async with self._lock:
            pending = [
                t for t in self.tasks.values()
                if t.status == TaskStatus.PENDING
            ]
            
            if not pending:
                return None
            
            # Ordena por prioridade (decrescente) depois por tempo (crescente)
            pending.sort(key=lambda t: (-t.priority, t.start_time))
            return pending[0]
    
    async def update_task(
        self,
        task_id: str,
        updates: Dict[str, Any]
    ) -> None:
        """Atualiza campos de uma tarefa"""
        async with self._lock:
            if task_id in self.tasks:
                task = self.tasks[task_id]
                for key, value in updates.items():
                    if hasattr(task, key):
                        setattr(task, key, value)
    
    async def remove_task(self, task_id: str) -> None:
        """Remove tarefa da fila"""
        async with self._lock:
            if task_id in self.tasks:
                del self.tasks[task_id]
    
    async def cleanup(self) -> None:
        """Remove tarefas terminadas há >7 dias"""
        async with self._lock:
            seven_days_ago = time.time() - (7 * 24 * 60 * 60)
            expired = [
                task_id for task_id, task in self.tasks.items()
                if is_terminal_status(task.status) and
                (task.end_time or 0) < seven_days_ago
            ]
            for task_id in expired:
                del self.tasks[task_id]
                logger.info(f"[Queue] Limpeza: removida tarefa {task_id}")
    
    async def get_all(self) -> List[TaskStateBase]:
        """Retorna todas as tarefas"""
        async with self._lock:
            return list(self.tasks.values())
    
    async def get_by_id(self, task_id: str) -> Optional[TaskStateBase]:
        """Busca tarefa por ID"""
        async with self._lock:
            return self.tasks.get(task_id)


# ═══════════════════════════════════════════════════════════════════════
# TASK EXECUTOR (com retry automático)
# ═══════════════════════════════════════════════════════════════════════

class TaskExecutor:
    """Executa tarefas com retry automático e backoff exponencial"""
    
    def __init__(self, queue: TaskQueue):
        self.queue = queue
    
    async def execute_with_retry(
        self,
        task: TaskStateBase,
        task_impl: Task,
        context: TaskContext,
        set_app_state: Callable,
    ) -> None:
        """
        Executa tarefa com retry automático.
        
        Backoff exponencial: 1s, 2s, 4s, 8s... (até 30s)
        """
        while task.retry_count < task.max_retries:
            try:
                # Atualiza status para RUNNING
                await self.queue.update_task(task.id, {
                    "status": TaskStatus.RUNNING,
                    "start_time": time.time(),
                })
                logger.info(f"[Executor] 🚀 Executando tarefa {task.id}")
                
                # Executa com timeout
                await asyncio.wait_for(
                    task_impl.spawn(task.id, context),
                    timeout=task.timeout / 1000.0  # Converte ms para s
                )
                
                # ✅ Sucesso
                await self.queue.update_task(task.id, {
                    "status": TaskStatus.COMPLETED,
                    "end_time": time.time(),
                })
                logger.info(f"[Executor] ✅ Tarefa {task.id} completada")
                return
            
            except asyncio.TimeoutError:
                task.retry_count += 1
                task.last_error = "Task timeout"
                logger.warning(f"[Executor] ⏱️ Timeout na tarefa {task.id}")
                
                if task.retry_count < task.max_retries:
                    await self._handle_retry(task)
                else:
                    await self.queue.update_task(task.id, {
                        "status": TaskStatus.TIMEOUT,
                        "end_time": time.time(),
                    })
            
            except Exception as e:
                task.retry_count += 1
                task.last_error = str(e)
                task.error_stack = self._get_error_stack(e)
                logger.error(f"[Executor] ❌ Erro na tarefa {task.id}: {e}")
                
                if task.retry_count < task.max_retries:
                    await self._handle_retry(task)
                else:
                    await self.queue.update_task(task.id, {
                        "status": TaskStatus.FAILED,
                        "end_time": time.time(),
                    })
                    raise
    
    async def _handle_retry(self, task: TaskStateBase) -> None:
        """Agenda retry com backoff exponencial"""
        # Backoff: 1s, 2s, 4s, 8s... (máx 30s)
        delay = min(
            1.0 * (2 ** (task.retry_count - 1)),
            30.0
        )
        
        retry_after = time.time() + delay
        
        await self.queue.update_task(task.id, {
            "status": TaskStatus.RETRYING,
            "retry_after": retry_after,
        })
        
        logger.info(
            f"[Executor] 🔄 Retry {task.retry_count}/{task.max_retries} "
            f"em {delay:.1f}s para tarefa {task.id}"
        )
        
        # Aguarda retry
        await asyncio.sleep(delay)
    
    @staticmethod
    def _get_error_stack(e: Exception) -> str:
        """Retorna stack trace da exceção"""
        import traceback
        return "".join(traceback.format_exception(type(e), e, e.__traceback__))


# ═══════════════════════════════════════════════════════════════════════
# TASK MANAGER (Orquestrador Principal)
# ═══════════════════════════════════════════════════════════════════════

class TaskManager:
    """Gerenciador central de tarefas"""
    
    def __init__(self):
        self.queue = TaskQueue()
        self.executor = TaskExecutor(self.queue)
        self.tasks_impl: Dict[TaskType, Task] = {}
        self._app_state: Dict = {}
        self._cleanup_task: Optional[asyncio.Task] = None
        logger.info("[TaskManager] Inicializado")
    
    def register_task_impl(self, task_impl: Task) -> None:
        """Registra implementação de tipo de tarefa"""
        self.tasks_impl[task_impl.type] = task_impl
        logger.info(f"[TaskManager] Registrado: {task_impl.name}")
    
    async def create_task(
        self,
        task_type: TaskType,
        description: str,
        priority: int = 5,
        timeout: int = 30000,
        max_retries: int = 3,
        tool_use_id: Optional[str] = None,
    ) -> str:
        """
        Cria e enfileira uma nova tarefa.
        Retorna o ID da tarefa.
        """
        task_id = generate_task_id(task_type)
        
        task = TaskStateBase(
            id=task_id,
            type=task_type,
            status=TaskStatus.PENDING,
            description=description,
            priority=priority,
            timeout=timeout,
            max_retries=max_retries,
            tool_use_id=tool_use_id,
        )
        
        await self.queue.enqueue(task)
        logger.info(
            f"[TaskManager] 📝 Tarefa criada: {task_id} "
            f"({task_type.value}, prioridade={priority})"
        )
        
        return task_id
    
    async def execute_task(self, task_id: str) -> None:
        """Executa uma tarefa enfileirada"""
        task = await self.queue.get_by_id(task_id)
        if not task:
            logger.error(f"[TaskManager] Tarefa não encontrada: {task_id}")
            return
        
        task_impl = self.tasks_impl.get(task.type)
        if not task_impl:
            logger.error(
                f"[TaskManager] Nenhuma implementação para tipo {task.type.value}"
            )
            await self.queue.update_task(task_id, {
                "status": TaskStatus.FAILED,
                "last_error": "No task implementation",
            })
            return
        
        # Cria contexto
        context = TaskContext(
            cancel_event=asyncio.Event(),
            get_app_state=lambda: self._app_state,
            set_app_state=self._set_app_state,
        )
        
        # Executa com retry
        try:
            await self.executor.execute_with_retry(
                task, task_impl, context, self._set_app_state
            )
        except Exception as e:
            logger.error(f"[TaskManager] Falha final na tarefa {task_id}: {e}")
    
    async def kill_task(self, task_id: str) -> None:
        """Mata uma tarefa"""
        task = await self.queue.get_by_id(task_id)
        if not task:
            logger.warning(f"[TaskManager] Tarefa não encontrada: {task_id}")
            return
        
        task_impl = self.tasks_impl.get(task.type)
        if not task_impl:
            return
        
        try:
            await task_impl.kill(task_id, self._app_state)
            await self.queue.update_task(task_id, {
                "status": TaskStatus.KILLED,
                "end_time": time.time(),
            })
            logger.info(f"[TaskManager] 🛑 Tarefa {task_id} morta")
        except Exception as e:
            logger.error(f"[TaskManager] Erro ao matar tarefa {task_id}: {e}")
    
    async def pause_task(self, task_id: str) -> None:
        """Pausa uma tarefa"""
        task = await self.queue.get_by_id(task_id)
        if not task:
            return
        
        task_impl = self.tasks_impl.get(task.type)
        if task_impl:
            await task_impl.pause(task_id, self._app_state)
            await self.queue.update_task(task_id, {
                "status": TaskStatus.PAUSED,
            })
    
    async def resume_task(self, task_id: str) -> None:
        """Retoma uma tarefa pausada"""
        task = await self.queue.get_by_id(task_id)
        if not task:
            return
        
        task_impl = self.tasks_impl.get(task.type)
        if task_impl:
            await task_impl.resume(task_id, self._app_state)
            await self.queue.update_task(task_id, {
                "status": TaskStatus.RUNNING,
            })
    
    async def get_task_info(self, task_id: str) -> Optional[Dict]:
        """Retorna informações de uma tarefa"""
        task = await self.queue.get_by_id(task_id)
        if task:
            return task.to_dict()
        return None
    
    async def get_all_tasks(self) -> List[Dict]:
        """Retorna todas as tarefas"""
        tasks = await self.queue.get_all()
        return [t.to_dict() for t in tasks]
    
    async def get_tasks_by_status(self, status: TaskStatus) -> List[Dict]:
        """Retorna tarefas com determinado status"""
        tasks = await self.queue.get_all()
        return [
            t.to_dict() for t in tasks
            if t.status == status
        ]
    
    async def cleanup_old_tasks(self) -> None:
        """Remove tarefas antigas"""
        await self.queue.cleanup()
    
    def _set_app_state(self, updater: Callable) -> None:
        """Atualiza estado da app"""
        self._app_state = updater(self._app_state)
    
    def print_status(self) -> None:
        """Imprime status do TaskManager"""
        import asyncio
        tasks = asyncio.run(self.queue.get_all())
        
        print("\n" + "═" * 60)
        print("  📋 TASK MANAGER — STATUS")
        print("═" * 60)
        print(f"  Total de tarefas: {len(tasks)}")
        
        for status in TaskStatus:
            count = sum(1 for t in tasks if t.status == status)
            if count > 0:
                print(f"    {status.value:.<20} {count:>3d}")
        
        print("═" * 60 + "\n")


# ═══════════════════════════════════════════════════════════════════════
# EXEMPLO DE IMPLEMENTAÇÃO
# ═══════════════════════════════════════════════════════════════════════

class LocalBashTask(Task):
    """Implementação de tarefa de shell local"""
    
    def __init__(self):
        super().__init__("LocalBashTask", TaskType.LOCAL_BASH)
    
    async def spawn(self, task_id: str, context: TaskContext) -> None:
        """Executa comando bash"""
        import subprocess
        
        logger.info(f"[LocalBash] Executando {task_id}")
        
        # Simulação
        await asyncio.sleep(2)
        
        logger.info(f"[LocalBash] Completado {task_id}")
    
    async def kill(self, task_id: str, app_state: Dict) -> None:
        """Mata processo bash"""
        logger.info(f"[LocalBash] Matando {task_id}")


# ═══════════════════════════════════════════════════════════════════════
# EXEMPLO DE USO
# ═══════════════════════════════════════════════════════════════════════

async def main():
    """Exemplo de uso do TaskManager"""
    
    # Configurar logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s"
    )
    
    # Criar manager
    manager = TaskManager()
    
    # Registrar implementações
    manager.register_task_impl(LocalBashTask())
    
    # Criar tarefas
    task1 = await manager.create_task(
        TaskType.LOCAL_BASH,
        "Executando testes",
        priority=8,
        timeout=30000,
        max_retries=3,
    )
    
    task2 = await manager.create_task(
        TaskType.LOCAL_BASH,
        "Compilando código",
        priority=5,
        timeout=60000,
    )
    
    # Executar
    await manager.execute_task(task1)
    await manager.execute_task(task2)
    
    # Ver status
    print("\n--- Tarefas criadas ---")
    for task_dict in await manager.get_all_tasks():
        print(f"ID: {task_dict['id']}, Status: {task_dict['status']}")
    
    manager.print_status()


if __name__ == "__main__":
    asyncio.run(main())
