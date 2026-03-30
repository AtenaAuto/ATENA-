import platform
import subprocess
import logging
from typing import Optional, Dict, Any
from .base import BaseActuator

logger = logging.getLogger("atena.actuator.system")

# Tentativas de import para funcionalidades extras
try:
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
    from comtypes import CLSCTX_ALL
    HAS_PYCAW = True
except ImportError:
    HAS_PYCAW = False

try:
    import ctypes
    HAS_CTYPES = True
except ImportError:
    HAS_CTYPES = False

class SystemActuator(BaseActuator):
    """
    Atuador para ações de sistema operacional:
      - Controle de volume (get/set)
      - Bloqueio de tela
      - Shutdown / restart / sleep / hibernate
      - Controle de brilho (experimental)
      - Execução segura com confirmação e dry-run
    """

    def __init__(self, dry_run: bool = False, confirm_destructive: bool = True):
        """
        Args:
            dry_run: Se True, apenas simula ações (não executa comandos reais).
            confirm_destructive: Se True, pede confirmação antes de shutdown/restart.
        """
        super().__init__()
        self.dry_run = dry_run
        self.confirm_destructive = confirm_destructive
        self._platform = platform.system()
        self._check_dependencies()
        self._volume_interface = None
        self._init_volume_interface()

    def _check_dependencies(self):
        """Verifica se as ferramentas necessárias estão disponíveis."""
        self._has_pactl = False
        self._has_amixer = False
        self._has_nircmd = False

        if self._platform == "Linux":
            # Verifica pactl
            try:
                subprocess.run(["pactl", "--version"], capture_output=True, check=True)
                self._has_pactl = True
                logger.info("pactl disponível para controle de volume")
            except (FileNotFoundError, subprocess.CalledProcessError):
                pass

            # Verifica amixer como fallback
            try:
                subprocess.run(["amixer", "--version"], capture_output=True, check=True)
                self._has_amixer = True
                logger.info("amixer disponível como fallback para volume")
            except (FileNotFoundError, subprocess.CalledProcessError):
                pass

            if not (self._has_pactl or self._has_amixer):
                logger.warning("Nenhuma ferramenta de volume encontrada (pactl/amixer)")

        elif self._platform == "Windows":
            # Verifica se pycaw está disponível
            if HAS_PYCAW:
                logger.info("pycaw disponível para controle avançado de volume")
            else:
                # Fallback: tentar nircmd (opcional)
                try:
                    subprocess.run(["nircmd", "version"], capture_output=True, check=True)
                    self._has_nircmd = True
                    logger.info("nircmd disponível como fallback para volume")
                except (FileNotFoundError, subprocess.CalledProcessError):
                    pass
                if not self._has_nircmd:
                    logger.warning("Nenhuma ferramenta de volume encontrada (pycaw ou nircmd)")

    def _init_volume_interface(self):
        """Inicializa interface de volume específica da plataforma."""
        if self._platform == "Windows" and HAS_PYCAW:
            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            self._volume_interface = interface.QueryInterface(IAudioEndpointVolume)

    def log_action(self, action: str, params: Optional[Dict[str, Any]] = None):
        """Registra ação no log e na base (via método herdado)."""
        msg = f"SystemActuator.{action}"
        if params:
            msg += f" {params}"
        logger.info(msg)
        # Se a classe base tiver um método de registro, chame-o
        if hasattr(super(), "log_action"):
            super().log_action(action, params)

    def _run_cmd(self, cmd: list, check: bool = True, capture: bool = False) -> Optional[str]:
        """Executa comando shell com tratamento de erros e dry-run."""
        if self.dry_run:
            logger.info(f"[DRY RUN] Simulando comando: {' '.join(cmd)}")
            return None

        try:
            if capture:
                result = subprocess.run(cmd, capture_output=True, text=True, check=check)
                return result.stdout.strip()
            else:
                subprocess.run(cmd, check=check)
                return None
        except subprocess.CalledProcessError as e:
            logger.error(f"Comando falhou: {' '.join(cmd)} - {e.stderr if capture else e}")
            raise RuntimeError(f"Falha ao executar comando: {e}")
        except FileNotFoundError as e:
            logger.error(f"Comando não encontrado: {cmd[0]}")
            raise RuntimeError(f"Comando não encontrado: {cmd[0]}") from e

    def _confirm_destructive(self, action: str) -> bool:
        """Pede confirmação do usuário para ações destrutivas."""
        if not self.confirm_destructive:
            return True
        resposta = input(f"⚠️  Confirmar {action} do sistema? (s/N): ").strip().lower()
        return resposta == 's'

    # ──────────────────────────────────────────────────────────────────
    # Volume
    # ──────────────────────────────────────────────────────────────────

    def get_volume(self) -> Optional[int]:
        """
        Retorna o volume atual (0-100) ou None se não suportado.
        """
        if self._platform == "Windows" and self._volume_interface:
            # pycaw: escala 0.0 a 1.0
            return int(self._volume_interface.GetMasterVolumeLevelScalar() * 100)

        elif self._platform == "Windows" and self._has_nircmd:
            # nircmd: precisa parsear a saída (exemplo simplificado)
            out = self._run_cmd(["nircmd", "changesysvolume"], capture=True)
            # Saída típica: "Current Volume: 65535" (0-65535)
            if out and "Current Volume:" in out:
                val = int(out.split(":")[1].strip())
                return int(val / 655.35)
            return None

        elif self._platform == "Linux":
            if self._has_pactl:
                out = self._run_cmd(["pactl", "get-sink-volume", "@DEFAULT_SINK@"], capture=True)
                # Exemplo: "Volume: front-left: 45875 /  70% / -9.23 dB"
                import re
                match = re.search(r"(\d+)%", out)
                if match:
                    return int(match.group(1))
            elif self._has_amixer:
                out = self._run_cmd(["amixer", "sget", "Master"], capture=True)
                # Exemplo: "Front Left: Playback 70 [70%]"
                import re
                match = re.search(r"\[(\d+)%\]", out)
                if match:
                    return int(match.group(1))
        return None

    def set_volume(self, level: int) -> None:
        """
        Ajusta volume (0-100). Lança exceção se não for possível.
        """
        if not 0 <= level <= 100:
            raise ValueError("Volume deve estar entre 0 e 100")

        if self.dry_run:
            self.log_action("set_volume", {"level": level, "dry_run": True})
            return

        if self._platform == "Windows":
            if self._volume_interface:
                self._volume_interface.SetMasterVolumeLevelScalar(level / 100.0, None)
                self.log_action("set_volume", {"level": level, "method": "pycaw"})
                return
            elif self._has_nircmd:
                # nircmd usa escala 0-65535
                val = int(level * 655.35)
                self._run_cmd(["nircmd", "setsysvolume", str(val)])
                self.log_action("set_volume", {"level": level, "method": "nircmd"})
                return
            else:
                # Fallback usando ctypes (API do Windows)
                if HAS_CTYPES:
                    try:
                        from ctypes import cast, POINTER
                        from comtypes import CLSCTX_ALL
                        # Código alternativo com win32api? Mas manteremos simples
                        raise NotImplementedError("Volume via ctypes não implementado")
                    except:
                        pass
                raise RuntimeError("Nenhum método de controle de volume disponível no Windows")

        elif self._platform == "Linux":
            if self._has_pactl:
                self._run_cmd(["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{level}%"])
            elif self._has_amixer:
                self._run_cmd(["amixer", "sset", "Master", f"{level}%"])
            else:
                raise RuntimeError("Nenhuma ferramenta de volume encontrada (pactl/amixer)")
            self.log_action("set_volume", {"level": level})

        elif self._platform == "Darwin":
            # macOS: usa osascript
            script = f"set volume output volume {level}"
            self._run_cmd(["osascript", "-e", script])
            self.log_action("set_volume", {"level": level})

        else:
            raise NotImplementedError(f"Controle de volume não suportado em {self._platform}")

    # ──────────────────────────────────────────────────────────────────
    # Ações do sistema
    # ──────────────────────────────────────────────────────────────────

    def lock_screen(self) -> None:
        """Bloqueia a tela."""
        if self.dry_run:
            self.log_action("lock_screen", {"dry_run": True})
            return

        if self._platform == "Linux":
            # Tenta vários comandos comuns
            for cmd in [["xdg-screensaver", "lock"],
                        ["gnome-screensaver-command", "--lock"],
                        ["loginctl", "lock-session"]]:
                try:
                    self._run_cmd(cmd)
                    self.log_action("lock_screen", {"method": cmd[0]})
                    return
                except RuntimeError:
                    continue
            raise RuntimeError("Nenhum comando de lock screen encontrado no Linux")

        elif self._platform == "Windows":
            self._run_cmd(["rundll32.exe", "user32.dll,LockWorkStation"])
            self.log_action("lock_screen")

        elif self._platform == "Darwin":
            self._run_cmd(["pmset", "displaysleepnow"])
            self.log_action("lock_screen")

        else:
            raise NotImplementedError(f"Lock screen não suportado em {self._platform}")

    def shutdown(self, delay: int = 0) -> None:
        """Desliga o computador após `delay` segundos."""
        if not self._confirm_destructive("shutdown"):
            self.log_action("shutdown_cancelled", {"delay": delay})
            return

        if self.dry_run:
            self.log_action("shutdown", {"delay": delay, "dry_run": True})
            return

        if self._platform == "Linux":
            cmd = ["shutdown", "-h", f"+{delay}" if delay else "now"]
        elif self._platform == "Windows":
            cmd = ["shutdown", "/s", "/t", str(delay)]
        elif self._platform == "Darwin":
            cmd = ["sudo", "shutdown", "-h", f"+{delay}" if delay else "now"]
        else:
            raise NotImplementedError(f"Shutdown não suportado em {self._platform}")

        self._run_cmd(cmd)
        self.log_action("shutdown", {"delay": delay})

    def restart(self, delay: int = 0) -> None:
        """Reinicia o computador após `delay` segundos."""
        if not self._confirm_destructive("restart"):
            self.log_action("restart_cancelled", {"delay": delay})
            return

        if self.dry_run:
            self.log_action("restart", {"delay": delay, "dry_run": True})
            return

        if self._platform == "Linux":
            cmd = ["shutdown", "-r", f"+{delay}" if delay else "now"]
        elif self._platform == "Windows":
            cmd = ["shutdown", "/r", "/t", str(delay)]
        elif self._platform == "Darwin":
            cmd = ["sudo", "shutdown", "-r", f"+{delay}" if delay else "now"]
        else:
            raise NotImplementedError(f"Restart não suportado em {self._platform}")

        self._run_cmd(cmd)
        self.log_action("restart", {"delay": delay})

    def sleep(self) -> None:
        """Coloca o computador em modo de suspensão (sleep)."""
        if self.dry_run:
            self.log_action("sleep", {"dry_run": True})
            return

        if self._platform == "Linux":
            # Tenta systemctl, pm-suspend, etc.
            for cmd in [["systemctl", "suspend"], ["pm-suspend"]]:
                try:
                    self._run_cmd(cmd)
                    self.log_action("sleep", {"method": cmd[0]})
                    return
                except RuntimeError:
                    continue
            raise RuntimeError("Nenhum comando de suspensão encontrado no Linux")
        elif self._platform == "Windows":
            # Usa rundll32 para suspender
            self._run_cmd(["rundll32.exe", "powrprof.dll,SetSuspendState", "0", "1", "0"])
            self.log_action("sleep")
        elif self._platform == "Darwin":
            self._run_cmd(["pmset", "sleepnow"])
            self.log_action("sleep")
        else:
            raise NotImplementedError(f"Sleep não suportado em {self._platform}")

    def hibernate(self) -> None:
        """Hiberna o computador."""
        if self.dry_run:
            self.log_action("hibernate", {"dry_run": True})
            return

        if self._platform == "Linux":
            try:
                self._run_cmd(["systemctl", "hibernate"])
                self.log_action("hibernate")
            except RuntimeError:
                raise RuntimeError("Hibernação não suportada ou systemctl não disponível")
        elif self._platform == "Windows":
            self._run_cmd(["shutdown", "/h"])
            self.log_action("hibernate")
        elif self._platform == "Darwin":
            # macOS não tem hibernação direta, mas deep sleep
            self._run_cmd(["pmset", "sleepnow"])  # fallback
            logger.warning("Hibernate não suportado nativamente no macOS, usando sleep")
        else:
            raise NotImplementedError(f"Hibernate não suportado em {self._platform}")

    # ──────────────────────────────────────────────────────────────────
    # Controle de brilho (experimental)
    # ──────────────────────────────────────────────────────────────────

    def set_brightness(self, level: int) -> None:
        """
        Ajusta brilho da tela (0-100). Suporte limitado a Linux (brightnessctl) e Windows (via powercfg ou WMI).
        """
        if not 0 <= level <= 100:
            raise ValueError("Brilho deve estar entre 0 e 100")

        if self.dry_run:
            self.log_action("set_brightness", {"level": level, "dry_run": True})
            return

        if self._platform == "Linux":
            # Tenta brightnessctl (mais comum)
            try:
                self._run_cmd(["brightnessctl", "set", f"{level}%"])
                self.log_action("set_brightness", {"level": level, "method": "brightnessctl"})
                return
            except RuntimeError:
                pass
            # Fallback: escrever diretamente em /sys/class/backlight/...
            import glob
            backlight = glob.glob("/sys/class/backlight/*/brightness")
            if backlight:
                max_brightness_file = backlight[0].replace("brightness", "max_brightness")
                try:
                    with open(max_brightness_file, 'r') as f:
                        max_val = int(f.read().strip())
                    new_val = int(max_val * level / 100)
                    with open(backlight[0], 'w') as f:
                        f.write(str(new_val))
                    self.log_action("set_brightness", {"level": level, "method": "sysfs"})
                    return
                except (IOError, OSError) as e:
                    logger.error(f"Falha ao escrever brilho via sysfs: {e}")
            raise RuntimeError("Nenhum método para controlar brilho no Linux (brightnessctl ou sysfs)")

        elif self._platform == "Windows":
            # Usa WMI via PowerShell (lento mas funciona)
            script = f"""
            $brightness = {level}
            $obj = Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods
            $obj.WmiSetBrightness(1, $brightness)
            """
            self._run_cmd(["powershell", "-Command", script])
            self.log_action("set_brightness", {"level": level, "method": "WMI"})

        else:
            raise NotImplementedError(f"Controle de brilho não suportado em {self._platform}")

    def get_brightness(self) -> Optional[int]:
        """Retorna o brilho atual (0-100) ou None se não suportado."""
        if self._platform == "Linux":
            import glob
            backlight = glob.glob("/sys/class/backlight/*/brightness")
            if backlight:
                max_file = backlight[0].replace("brightness", "max_brightness")
                try:
                    with open(backlight[0], 'r') as f:
                        cur = int(f.read().strip())
                    with open(max_file, 'r') as f:
                        maxv = int(f.read().strip())
                    return int(cur * 100 / maxv)
                except:
                    pass
            # Fallback com brightnessctl
            out = self._run_cmd(["brightnessctl", "g"], capture=True)
            if out:
                try:
                    cur = int(out.strip())
                    # precisa do max
                    max_out = self._run_cmd(["brightnessctl", "m"], capture=True)
                    if max_out:
                        maxv = int(max_out.strip())
                        return int(cur * 100 / maxv)
                except:
                    pass
            return None
        elif self._platform == "Windows":
            # via PowerShell
            out = self._run_cmd(["powershell", "(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightness).CurrentBrightness"], capture=True)
            if out and out.isdigit():
                return int(out)
            return None
        return None
