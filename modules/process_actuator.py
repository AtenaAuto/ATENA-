import subprocess
import psutil
from .base import BaseActuator

class ProcessActuator(BaseActuator):
    """Gerenciamento de processos."""
    def _check_dependencies(self):
        # psutil já instalado
        pass

    def run_command(self, command: list, shell=False, timeout=None):
        """Executa um comando e retorna (stdout, stderr, returncode)."""
        try:
            result = subprocess.run(
                command,
                shell=shell,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            self.log_action("run_command", {"command": command, "returncode": result.returncode})
            return result.stdout, result.stderr, result.returncode
        except subprocess.TimeoutExpired as e:
            self.log_action("run_command_timeout", {"command": command})
            return e.stdout, e.stderr, -1

    def get_process_info(self, pid: int):
        """Obtém informações de um processo pelo PID."""
        try:
            p = psutil.Process(pid)
            info = {
                "name": p.name(),
                "status": p.status(),
                "cpu_percent": p.cpu_percent(),
                "memory_percent": p.memory_percent(),
                "create_time": p.create_time(),
                "cmdline": p.cmdline()
            }
            return info
        except psutil.NoSuchProcess:
            return None

    def kill_process(self, pid: int, force=False):
        """Encerra um processo."""
        try:
            p = psutil.Process(pid)
            if force:
                p.kill()
            else:
                p.terminate()
            self.log_action("kill_process", {"pid": pid, "force": force})
            return True
        except psutil.NoSuchProcess:
            return False
