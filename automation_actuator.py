# modules/automation_actuator.py
import time
import threading
from .base import BaseActuator

class AutomationActuator(BaseActuator):
    """Automação de teclado/mouse."""
    def __init__(self, sysaware=None, safety_switch=True):
        self.safety_switch = safety_switch
        self._enabled = True
        self._pyautogui = None
        super().__init__(sysaware)

    def _check_dependencies(self):
        try:
            import pyautogui
            self._pyautogui = pyautogui
            self._pyautogui.FAILSAFE = True
            self._pyautogui.PAUSE = 0.1
        except ImportError:
            raise ImportError("pyautogui não instalado. Execute: pip install pyautogui")

    def enable(self):
        if self.safety_switch:
            self._enabled = True

    def disable(self):
        self._enabled = False

    def _check_enabled(self):
        if not self._enabled:
            raise RuntimeError("Automação desabilitada pelo safety_switch")

    def move_mouse(self, x, y, duration=0.2):
        self._check_enabled()
        self._pyautogui.moveTo(x, y, duration=duration)

    def click(self, button='left', x=None, y=None):
        self._check_enabled()
        if x is not None and y is not None:
            self._pyautogui.click(x, y, button=button)
        else:
            self._pyautogui.click(button=button)

    def type_text(self, text, interval=0.05):
        self._check_enabled()
        self._pyautogui.typewrite(text, interval=interval)

    def press_key(self, key):
        self._check_enabled()
        self._pyautogui.press(key)

    def screenshot(self, region=None, filename=None):
        self._check_enabled()
        img = self._pyautogui.screenshot(region=region)
        if filename:
            img.save(filename)
        return img
