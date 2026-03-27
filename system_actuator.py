import platform
import subprocess
from .base import BaseActuator

class SystemActuator(BaseActuator):
    """Ajustes simples do sistema."""
    def _check_dependencies(self):
        self._platform = platform.system()

    def set_volume(self, level: int):
        """Ajusta volume (0-100). Linux requer pactl; Windows via comando."""
        if self._platform == "Linux":
            try:
                subprocess.run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{level}%"], check=True)
                self.log_action("set_volume", {"level": level})
            except FileNotFoundError:
                raise RuntimeError("pactl não encontrado. Instale pulseaudio-utils.")
        elif self._platform == "Windows":
            # Usa comando powershell
            subprocess.run(["powershell", f"(New-Object -ComObject WScript.Shell).SendKeys([char]175)"])  # aumentar
            # Mais preciso: usar nircmd ou lib específica
            raise NotImplementedError("Controle de volume no Windows requer biblioteca adicional.")
        else:
            raise NotImplementedError(f"Sistema {self._platform} não suportado.")

    def lock_screen(self):
        """Bloqueia a tela."""
        if self._platform == "Linux":
            subprocess.run(["xdg-screensaver", "lock"])
        elif self._platform == "Windows":
            subprocess.run(["rundll32.exe", "user32.dll,LockWorkStation"])
        elif self._platform == "Darwin":
            subprocess.run(["pmset", "displaysleepnow"])
        self.log_action("lock_screen")

    def shutdown(self, delay=0):
        """Desliga o computador (cuidado!)."""
        if self._platform == "Linux":
            subprocess.run(["shutdown", "-h", f"+{delay}" if delay else "now"])
        elif self._platform == "Windows":
            subprocess.run(["shutdown", "/s", "/t", str(delay)])
        elif self._platform == "Darwin":
            subprocess.run(["sudo", "shutdown", "-h", f"+{delay}" if delay else "now"])
        self.log_action("shutdown", {"delay": delay})
