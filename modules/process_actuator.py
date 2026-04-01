import subprocess
import psutil
import time
import signal
import logging
from typing import List, Dict, Optional, Tuple, Union, Any
from pathlib import Path
from .base import BaseActuator

logger = logging.getLogger("atena.actuator.process")

class ProcessActuator(BaseActuator):
    """
    Atuador para gerenciamento de processos do sistema:
      - Execuo de comandos com timeout e captura de sada
      - Informaes detalhadas de processos (CPU, memria, cmdline)
      - Encerramento seguro (terminate/kill)
      - Busca por nome/PID
      - Espera por trmino de processo
      - Listagem de processos com filtros
    """

    def __init__(self, command_whitelist: Optional[List[str]] = None):
        """
        Args:
            command_whitelist: Lista de comandos permitidos (None = todos permitidos).
                               Ex: ["ls", "ping", "python"]
        """
        super().__init__()
        self.command_whitelist = command_whitelist
        self._check_dependencies()

    def _check_dependencies(self):
        """Verifica se psutil est disponvel."""
        if not hasattr(psutil, "__version__"):
            raise ImportError("psutil no est instalado. Execute: pip install psutil")
        logger.info("ProcessActuator inicializado com psutil %s", psutil.__version__)

    def log_action(self, action: str, params: Optional[Dict[str, Any]] = None):
        """Registra ao com contexto."""
        msg = f"ProcessActuator.{action}"
        if params:
            # Remove dados sensveis como comandos completos se necessrio
            safe_params = {k: v for k, v in (params or {}).items() if k != "command"}
            msg += f" {safe_params}"
        logger.info(msg)
        if hasattr(super(), "log_action"):
            super().log_action(action, params)

    def _is_command_allowed(self, command: Union[str, List[str]]) -> bool:
        """Verifica se o comando est na whitelist (se configurada)."""
        if self.command_whitelist is None:
            return True
        cmd_str = command if isinstance(command, str) else command[0]
        base_cmd = Path(cmd_str).name
        return base_cmd in self.command_whitelist

    # 
    # Execuo de comandos
    # 

    def run_command(
        self,
        command: Union[str, List[str]],
        shell: bool = False,
        timeout: Optional[float] = None,
        input_data: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
        cwd: Optional[Union[str, Path]] = None,
        kill_on_timeout: bool = True
    ) -> Tuple[str, str, int]:
        """
        Executa um comando e retorna (stdout, stderr, returncode).

        Args:
            command: Lista de argumentos ou string (se shell=True).
            shell: Se True, usa shell (cuidado: riscos de segurana).
            timeout: Tempo mximo em segundos.
            input_data: String enviada para stdin do processo.
            env: Dicionrio de variveis de ambiente.
            cwd: Diretrio de trabalho.
            kill_on_timeout: Se True, mata o processo aps timeout (caso contrrio, apenas cancela a espera).

        Returns:
            (stdout, stderr, returncode)
        """
        if not self._is_command_allowed(command):
            raise PermissionError(f"Comando no autorizado pela whitelist: {command}")

        # Aviso sobre shell inseguro
        if shell and isinstance(command, str):
            logger.warning("Uso de shell=True com comando string: %s - risco de injeo", command)

        try:
            result = subprocess.run(
                command,
                shell=shell,
                capture_output=True,
                text=True,
                timeout=timeout,
                input=input_data,
                env=env,
                cwd=str(cwd) if cwd else None
            )
            self.log_action("run_command", {"command": command, "returncode": result.returncode})
            return result.stdout, result.stderr, result.returncode

        except subprocess.TimeoutExpired as e:
            self.log_action("run_command_timeout", {"command": command, "timeout": timeout})
            if kill_on_timeout and e.process:
                try:
                    e.process.kill()
                    e.process.wait()
                except Exception:
                    pass
            return e.stdout, e.stderr, -1

        except FileNotFoundError as e:
            self.log_action("run_command_fnf", {"command": command})
            raise RuntimeError(f"Comando no encontrado: {command}") from e

        except PermissionError as e:
            self.log_action("run_command_permission", {"command": command})
            raise RuntimeError(f"Permisso negada para executar: {command}") from e

    # 
    # Informaes de processo
    # 

    def get_process_info(self, pid: int) -> Optional[Dict[str, Any]]:
        """
        Obtm informaes detalhadas de um processo pelo PID.

        Returns:
            Dicionrio com campos ou None se processo no existir.
        """
        try:
            p = psutil.Process(pid)
            with p.oneshot():  # Otimizao para mltiplas chamadas
                info = {
                    "pid": pid,
                    "name": p.name(),
                    "exe": p.exe(),
                    "status": p.status(),
                    "cpu_percent": p.cpu_percent(interval=0.1),
                    "memory_percent": p.memory_percent(),
                    "memory_rss": p.memory_info().rss,
                    "create_time": p.create_time(),
                    "cmdline": p.cmdline(),
                    "username": p.username(),
                    "num_threads": p.num_threads(),
                    "connections": len(p.connections(kind='inet')),
                }
            return info
        except psutil.NoSuchProcess:
            logger.debug(f"Processo {pid} no encontrado")
            return None
        except (psutil.AccessDenied, psutil.ZombieProcess) as e:
            logger.warning(f"Sem acesso ao processo {pid}: {e}")
            return None

    def get_process_by_name(self, name: str, partial: bool = False) -> List[Dict[str, Any]]:
        """
        Retorna informaes de todos os processos com determinado nome.

        Args:
            name: Nome do executvel (ex: "python", "chrome.exe").
            partial: Se True, faz correspondncia parcial (substring).
        """
        results = []
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                proc_name = proc.info['name']
                if partial:
                    match = name.lower() in (proc_name or "").lower()
                else:
                    match = name.lower() == (proc_name or "").lower()
                if match:
                    info = self.get_process_info(proc.info['pid'])
                    if info:
                        results.append(info)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return results

    def is_process_running(self, pid: int) -> bool:
        """Verifica se um processo com o PID est ativo."""
        return psutil.pid_exists(pid)

    def list_processes(
        self,
        filter_by: Optional[str] = None,
        sort_by: str = "pid",
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Lista processos do sistema com filtros opcionais.

        Args:
            filter_by: Filtro por nome (substring, case-insensitive).
            sort_by: Campo para ordenao ("pid", "name", "cpu_percent", "memory_percent").
            limit: Nmero mximo de processos retornados.
        """
        processes = []
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
            try:
                info = proc.info
                if filter_by:
                    if filter_by.lower() not in (info['name'] or "").lower():
                        continue
                processes.append(info)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        # Ordenao
        if sort_by in ["pid", "cpu_percent", "memory_percent"]:
            processes.sort(key=lambda x: x.get(sort_by, 0))
        elif sort_by == "name":
            processes.sort(key=lambda x: x.get('name', ''))
        else:
            processes.sort(key=lambda x: x.get('pid', 0))

        if limit:
            processes = processes[:limit]
        return processes

    def get_all_processes_info(self) -> List[Dict[str, Any]]:
        """Retorna informaes de todos os processos (pode ser pesado)."""
        infos = []
        for pid in psutil.pids():
            info = self.get_process_info(pid)
            if info:
                infos.append(info)
        return infos

    # 
    # Controle de processos
    # 

    def kill_process(self, pid: int, force: bool = False, graceful_timeout: float = 5.0) -> bool:
        """
        Encerra um processo.

        Args:
            pid: ID do processo.
            force: Se True, usa `kill()` (SIGKILL); caso contrrio, `terminate()` (SIGTERM).
            graceful_timeout: Se force=False, aguarda esse tempo antes de forar kill.

        Returns:
            True se o processo foi encerrado ou j no existia; False em erro.
        """
        try:
            p = psutil.Process(pid)
            if not p.is_running():
                logger.debug(f"Processo {pid} j no est em execuo")
                return True

            if force:
                logger.info(f"Forando kill do processo {pid}")
                p.kill()
            else:
                logger.info(f"Encerrando processo {pid} com SIGTERM")
                p.terminate()
                # Aguarda trmino gracioso
                gone, alive = psutil.wait_procs([p], timeout=graceful_timeout)
                if alive:
                    logger.warning(f"Processo {pid} no respondeu, forando kill")
                    p.kill()
            self.log_action("kill_process", {"pid": pid, "force": force})
            return True

        except psutil.NoSuchProcess:
            logger.debug(f"Processo {pid} no existe mais")
            return True
        except (psutil.AccessDenied, PermissionError) as e:
            logger.error(f"Sem permisso para encerrar processo {pid}: {e}")
            return False

    def kill_process_by_name(self, name: str, force: bool = False) -> int:
        """
        Encerra todos os processos com o nome dado.

        Returns:
            Nmero de processos encerrados.
        """
        killed = 0
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                if proc.info['name'] and proc.info['name'].lower() == name.lower():
                    if self.kill_process(proc.info['pid'], force=force):
                        killed += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        self.log_action("kill_process_by_name", {"name": name, "count": killed})
        return killed

    def wait_for_process(self, pid: int, timeout: float = 30.0, poll_interval: float = 0.5) -> bool:
        """
        Aguarda at que o processo termine.

        Returns:
            True se o processo terminou dentro do timeout, False caso contrrio.
        """
        start = time.time()
        while time.time() - start < timeout:
            if not self.is_process_running(pid):
                return True
            time.sleep(poll_interval)
        return False

    def wait_for_process_by_name(self, name: str, timeout: float = 30.0) -> bool:
        """
        Aguarda at que nenhum processo com o nome dado esteja em execuo.
        """
        start = time.time()
        while time.time() - start < timeout:
            processes = self.get_process_by_name(name)
            if not processes:
                return True
            time.sleep(0.5)
        return False

    # 
    # Utilitrios
    # 

    def get_current_process_info(self) -> Dict[str, Any]:
        """Retorna informaes do prprio processo Atena."""
        import os
        return self.get_process_info(os.getpid())

    def get_parent_process_info(self) -> Optional[Dict[str, Any]]:
        """Retorna informaes do processo pai."""
        try:
            parent_pid = psutil.Process().ppid()
            return self.get_process_info(parent_pid)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return None
