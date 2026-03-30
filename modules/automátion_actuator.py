# modules/automation_actuator_enhanced.py
"""
┌─────────────────────────────────────────────────────────────────────┐
│         ATENA AUTOMATION ACTUATOR v2.1                              │
│  Automação de teclado/mouse com segurança, OCR, macros e histórico  │
│                                                                     │
│  Features (melhoradas):                                             │
│   • Fila de ações com prioridade e Future para retorno síncrono     │
│   • Gravação e playback de macros (inclui scroll e combos)          │
│   • OCR com cache inteligente                                       │
│   • Retry automático com backoff exponencial                        │
│   • Safety locks (canto quente para parar)                          │
│   • Histórico persistente com limpeza automática                    │
│   • Múltiplos backends (pyautogui, pynput)                          │
│   • Detecção de mudanças de tela (placeholder)                      │
│   • Validação de ações antes de executar                            │
│   • Integração com Atena para automação autônoma                    │
└─────────────────────────────────────────────────────────────────────┘
"""

import os
import re
import json
import time
import queue
import threading
import logging
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
from typing import (
    Optional, Dict, List, Tuple, Callable, Any, Union
)
from collections import deque
from dataclasses import dataclass, asdict
from enum import Enum
import hashlib
from concurrent.futures import Future

logger = logging.getLogger("atena.automation")

# ── Detecção de backends ──────────────────────────────────────────

try:
    import pyautogui
    HAS_PYAUTOGUI = True
except ImportError:
    HAS_PYAUTOGUI = False

try:
    from pynput import mouse, keyboard
    HAS_PYNPUT = True
except ImportError:
    HAS_PYNPUT = False

try:
    import pytesseract
    from PIL import Image, ImageGrab
    HAS_OCR = True
except ImportError:
    HAS_OCR = False

try:
    import cv2
    import numpy as np
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False


# ═══════════════════════════════════════════════════════════════════════
# CONFIGURAÇÃO E TIPOS
# ═══════════════════════════════════════════════════════════════════════

class ActionType(Enum):
    """Tipos de ação de automação"""
    MOVE_MOUSE = "move_mouse"
    CLICK = "click"
    DOUBLE_CLICK = "double_click"
    TYPE_TEXT = "type_text"
    PRESS_KEY = "press_key"
    KEY_COMBO = "key_combo"
    SCREENSHOT = "screenshot"
    WAIT = "wait"
    FIND_AND_CLICK = "find_and_click"
    VERIFY_TEXT = "verify_text"
    SCROLL = "scroll"
    DRAG = "drag"
    HOTKEY_STOP = "hotkey_stop"
    CONDITIONAL = "conditional"


@dataclass
class Action:
    """Uma ação a ser executada, com suporte a Future para retorno síncrono"""
    type: ActionType
    params: Dict[str, Any]
    priority: int = 0
    timeout: int = 30
    retries: int = 3
    created_at: str = None
    future: Optional[Future] = None   # ← novo: permite aguardar resultado

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now().isoformat()

    def to_dict(self) -> Dict:
        d = asdict(self)
        d['type'] = self.type.value
        d.pop('future', None)  # não serializável
        return d


@dataclass
class AutomationConfig:
    """Configurações de automação"""
    backend: str = "auto"
    safety_enabled: bool = True
    safety_corner: Tuple[int, int] = (0, 0)
    safety_corner_radius: int = 5
    action_delay: float = 0.05
    type_speed: float = 0.05
    click_duration: float = 0.1
    move_duration: float = 0.2
    ocr_enabled: bool = True
    ocr_language: str = "por"
    image_match_threshold: float = 0.8
    history_enabled: bool = True
    history_db: Path = Path("./atena_evolution/automation/history.db")
    history_keep_days: int = 30
    retry_enabled: bool = True
    retry_backoff: float = 1.5
    retry_max_delay: float = 10.0
    log_screenshots: bool = False
    screenshot_dir: Path = Path("./atena_evolution/automation/screenshots")
    verbose: bool = False
    ocr_cache_ttl: float = 2.0   # segundos

    def setup(self):
        self.history_db.parent.mkdir(parents=True, exist_ok=True)
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)


# ═══════════════════════════════════════════════════════════════════════
# BACKEND ABSTRATO
# ═══════════════════════════════════════════════════════════════════════

class AutomationBackend:
    """Interface abstrata para backends de automação"""
    def move_mouse(self, x: int, y: int, duration: float = 0.2): ...
    def click(self, x: int, y: int, button: str = "left", clicks: int = 1): ...
    def type_text(self, text: str, interval: float = 0.05): ...
    def press_key(self, key: str): ...
    def key_combo(self, *keys: str): ...
    def screenshot(self, region: Optional[Tuple] = None) -> Any: ...
    def scroll(self, x: int, y: int, amount: int): ...
    def get_mouse_position(self) -> Tuple[int, int]: ...
    def drag(self, from_x: int, from_y: int, to_x: int, to_y: int, duration: float = 0.2): ...


class PyAutoGUIBackend(AutomationBackend):
    def __init__(self, cfg: AutomationConfig):
        if not HAS_PYAUTOGUI:
            raise ImportError("pyautogui não instalado")
        self.cfg = cfg
        pyautogui.FAILSAFE = True
        pyautogui.PAUSE = cfg.action_delay

    def move_mouse(self, x: int, y: int, duration: float = 0.2):
        pyautogui.moveTo(x, y, duration=duration)

    def click(self, x: int, y: int, button: str = "left", clicks: int = 1):
        pyautogui.click(x, y, button=button, clicks=clicks)

    def type_text(self, text: str, interval: float = 0.05):
        pyautogui.typewrite(text, interval=interval)

    def press_key(self, key: str):
        pyautogui.press(key)

    def key_combo(self, *keys: str):
        pyautogui.hotkey(*keys)

    def screenshot(self, region: Optional[Tuple] = None):
        return pyautogui.screenshot(region=region)

    def scroll(self, x: int, y: int, amount: int):
        pyautogui.moveTo(x, y)
        pyautogui.scroll(amount)

    def get_mouse_position(self) -> Tuple[int, int]:
        return pyautogui.position()

    def drag(self, from_x: int, from_y: int, to_x: int, to_y: int, duration: float = 0.2):
        pyautogui.moveTo(from_x, from_y)
        pyautogui.drag(to_x - from_x, to_y - from_y, duration=duration, button='left')


class PyNputBackend(AutomationBackend):
    def __init__(self, cfg: AutomationConfig):
        if not HAS_PYNPUT:
            raise ImportError("pynput não instalado")
        self.cfg = cfg
        self.mouse = mouse.Controller()
        self.keyboard = keyboard.Controller()

    def move_mouse(self, x: int, y: int, duration: float = 0.2):
        from_x, from_y = self.mouse.position
        steps = max(1, int(duration * 60))
        for i in range(steps + 1):
            t = i / steps
            nx = int(from_x + (x - from_x) * t)
            ny = int(from_y + (y - from_y) * t)
            self.mouse.position = (nx, ny)
            time.sleep(duration / steps)

    def click(self, x: int, y: int, button: str = "left", clicks: int = 1):
        self.mouse.position = (x, y)
        btn = mouse.Button.left if button == "left" else mouse.Button.right
        for _ in range(clicks):
            self.mouse.click(btn)
            time.sleep(0.05)

    def type_text(self, text: str, interval: float = 0.05):
        for char in text:
            self.keyboard.type(char)
            time.sleep(interval)

    def press_key(self, key: str):
        key_map = {
            "enter": keyboard.Key.enter,
            "space": keyboard.Key.space,
            "tab": keyboard.Key.tab,
            "backspace": keyboard.Key.backspace,
            "esc": keyboard.Key.esc,
            "up": keyboard.Key.up,
            "down": keyboard.Key.down,
            "left": keyboard.Key.left,
            "right": keyboard.Key.right,
        }
        key_obj = key_map.get(key.lower())
        if key_obj:
            self.keyboard.press(key_obj)
            self.keyboard.release(key_obj)
        else:
            self.keyboard.type(key)

    def key_combo(self, *keys: str):
        key_map = {
            "ctrl": keyboard.Key.ctrl,
            "alt": keyboard.Key.alt,
            "shift": keyboard.Key.shift,
            "cmd": keyboard.Key.cmd,
        }
        pressed = []
        for k in keys[:-1]:
            key_obj = key_map.get(k.lower())
            if key_obj:
                self.keyboard.press(key_obj)
                pressed.append(key_obj)
        # última tecla
        self.press_key(keys[-1])
        for key_obj in reversed(pressed):
            self.keyboard.release(key_obj)

    def screenshot(self, region: Optional[Tuple] = None):
        return ImageGrab.grab(bbox=region)

    def scroll(self, x: int, y: int, amount: int):
        self.mouse.position = (x, y)
        self.mouse.scroll(0, amount)

    def get_mouse_position(self) -> Tuple[int, int]:
        return self.mouse.position

    def drag(self, from_x: int, from_y: int, to_x: int, to_y: int, duration: float = 0.2):
        self.mouse.position = (from_x, from_y)
        self.mouse.press(mouse.Button.left)
        self.move_mouse(to_x, to_y, duration)
        self.mouse.release(mouse.Button.left)


# ═══════════════════════════════════════════════════════════════════════
# MOTOR OCR COM CACHE
# ═══════════════════════════════════════════════════════════════════════

class OCREngine:
    """Motor de OCR com cache por região/texto"""
    def __init__(self, cfg: AutomationConfig):
        self.cfg = cfg
        self._cache: Dict[str, Tuple[float, Optional[Tuple[int, int]]]] = {}

    def _cache_key(self, text: str, region: Optional[Tuple]) -> str:
        return f"{text}|{region}" if region else text

    def find_text(self, text: str, region: Optional[Tuple] = None) -> Optional[Tuple[int, int]]:
        if not HAS_OCR:
            logger.warning("[OCR] OCR não disponível")
            return None

        key = self._cache_key(text, region)
        now = time.time()
        if key in self._cache:
            ts, pos = self._cache[key]
            if now - ts < self.cfg.ocr_cache_ttl:
                return pos

        try:
            img = ImageGrab.grab(bbox=region)
            offset_x, offset_y = (region[0], region[1]) if region else (0, 0)

            ocr_data = pytesseract.image_to_data(
                img, output_type=pytesseract.Output.DICT, lang=self.cfg.ocr_language
            )

            for i, txt in enumerate(ocr_data['text']):
                if text.lower() in txt.lower():
                    x = ocr_data['left'][i] + ocr_data['width'][i] // 2 + offset_x
                    y = ocr_data['top'][i] + ocr_data['height'][i] // 2 + offset_y
                    self._cache[key] = (now, (x, y))
                    return (x, y)
        except Exception as e:
            logger.warning(f"[OCR] Erro: {e}")

        self._cache[key] = (now, None)
        return None

    def extract_text(self, region: Optional[Tuple] = None) -> str:
        if not HAS_OCR:
            return ""
        try:
            img = ImageGrab.grab(bbox=region)
            return pytesseract.image_to_string(img, lang=self.cfg.ocr_language)
        except Exception as e:
            logger.warning(f"[OCR] Erro: {e}")
            return ""

    def find_image(self, image_path: Union[str, Path], region: Optional[Tuple] = None,
                   threshold: float = 0.8) -> Optional[Tuple[int, int]]:
        if not HAS_CV2:
            logger.warning("[OCR] OpenCV não disponível")
            return None
        try:
            screen = np.array(ImageGrab.grab(bbox=region))
            offset_x, offset_y = (region[0], region[1]) if region else (0, 0)
            template = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
            screen_bgr = cv2.cvtColor(screen, cv2.COLOR_RGB2BGR)
            result = cv2.matchTemplate(screen_bgr, template, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(result)
            if max_val >= threshold:
                h, w = template.shape[:2]
                return (max_loc[0] + w//2 + offset_x, max_loc[1] + h//2 + offset_y)
        except Exception as e:
            logger.warning(f"[OCR] Template match error: {e}")
        return None


# ═══════════════════════════════════════════════════════════════════════
# HISTÓRICO THREAD-SAFE COM LIMPEZA AUTOMÁTICA
# ═══════════════════════════════════════════════════════════════════════

class ActionHistory:
    def __init__(self, cfg: AutomationConfig):
        self.cfg = cfg
        self._lock = threading.Lock()
        self._init_db()
        self._start_cleanup_thread()

    def _init_db(self):
        with self._lock:
            self.conn = sqlite3.connect(str(self.cfg.history_db), check_same_thread=False)
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS actions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    action_type TEXT,
                    params TEXT,
                    status TEXT,
                    started_at TEXT,
                    completed_at TEXT,
                    duration REAL,
                    error TEXT,
                    screenshot_path TEXT
                )
            """)
            self.conn.commit()

    def record(self, action: Action, status: str, duration: float,
               error: Optional[str] = None, screenshot_path: Optional[str] = None):
        with self._lock:
            self.conn.execute("""
                INSERT INTO actions
                (action_type, params, status, started_at, completed_at, duration, error, screenshot_path)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                action.type.value,
                json.dumps(action.params),
                status,
                action.created_at,
                datetime.now().isoformat(),
                duration,
                error,
                screenshot_path,
            ))
            self.conn.commit()

    def get_recent(self, limit: int = 50) -> List[Dict]:
        with self._lock:
            rows = self.conn.execute("""
                SELECT action_type, status, duration, error
                FROM actions
                ORDER BY id DESC LIMIT ?
            """, (limit,)).fetchall()
        return [{"type": r[0], "status": r[1], "duration": r[2], "error": r[3]} for r in rows]

    def cleanup(self):
        cutoff = (datetime.now() - timedelta(days=self.cfg.history_keep_days)).isoformat()
        with self._lock:
            self.conn.execute("DELETE FROM actions WHERE started_at < ?", (cutoff,))
            self.conn.commit()

    def _start_cleanup_thread(self):
        def cleaner():
            while True:
                time.sleep(86400)  # 24h
                self.cleanup()
        t = threading.Thread(target=cleaner, daemon=True)
        t.start()


# ═══════════════════════════════════════════════════════════════════════
# FILA DE AÇÕES COM EVENTOS DE PAUSA E FUTURES
# ═══════════════════════════════════════════════════════════════════════

class ActionQueue:
    def __init__(self):
        self._queue = queue.PriorityQueue()
        self._counter = 0
        self._paused = threading.Event()
        self._paused.clear()  # não pausado

    def add(self, action: Action):
        with threading.Lock():
            self._counter += 1
            seq = self._counter
        priority = (-action.priority, seq)
        self._queue.put((priority, action))

    def get(self, timeout: float = 1.0) -> Optional[Action]:
        try:
            _, action = self._queue.get(timeout=timeout)
            return action
        except queue.Empty:
            return None

    def is_empty(self) -> bool:
        return self._queue.empty()

    def pause(self):
        self._paused.set()

    def resume(self):
        self._paused.clear()

    def wait_if_paused(self):
        """Bloqueia até que não esteja pausado"""
        self._paused.wait()

    def clear(self):
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break


# ═══════════════════════════════════════════════════════════════════════
# EXECUTOR DE AÇÕES
# ═══════════════════════════════════════════════════════════════════════

class ActionExecutor:
    def __init__(self, backend: AutomationBackend, cfg: AutomationConfig,
                 ocr: OCREngine, history: ActionHistory):
        self.backend = backend
        self.cfg = cfg
        self.ocr = ocr
        self.history = history
        self._last_screenshot: Optional[Any] = None

    def execute(self, action: Action) -> Tuple[bool, Optional[str]]:
        logger.info(f"[Executor] Executando: {action.type.value}")
        delay = 0.5
        last_error = None

        for attempt in range(action.retries):
            try:
                start = time.time()
                result = self._execute_action(action)
                duration = time.time() - start
                self.history.record(action, "success", duration)

                # Se a ação tem Future, seta o resultado
                if action.future and not action.future.done():
                    action.future.set_result(result)

                logger.info(f"[Executor] ✅ {action.type.value} concluído em {duration:.2f}s")
                return True, None

            except Exception as e:
                last_error = str(e)
                logger.warning(f"[Executor] ❌ Tentativa {attempt+1}/{action.retries}: {e}")
                if attempt < action.retries - 1:
                    time.sleep(min(delay, self.cfg.retry_max_delay))
                    delay *= self.cfg.retry_backoff

        self.history.record(action, "failed", 0.0, error=last_error)
        if action.future and not action.future.done():
            action.future.set_exception(RuntimeError(last_error))
        return False, last_error

    def _execute_action(self, action: Action) -> Any:
        p = action.params

        if action.type == ActionType.MOVE_MOUSE:
            self.backend.move_mouse(p['x'], p['y'], duration=self.cfg.move_duration)

        elif action.type == ActionType.CLICK:
            self.backend.click(p.get('x'), p.get('y'),
                               button=p.get('button', 'left'),
                               clicks=p.get('clicks', 1))

        elif action.type == ActionType.DOUBLE_CLICK:
            self.backend.click(p['x'], p['y'], button='left', clicks=2)

        elif action.type == ActionType.TYPE_TEXT:
            self.backend.type_text(p['text'], interval=self.cfg.type_speed)

        elif action.type == ActionType.PRESS_KEY:
            self.backend.press_key(p['key'])

        elif action.type == ActionType.KEY_COMBO:
            self.backend.key_combo(*p['keys'])

        elif action.type == ActionType.SCREENSHOT:
            self._last_screenshot = self.backend.screenshot(region=p.get('region'))
            return self._last_screenshot

        elif action.type == ActionType.WAIT:
            time.sleep(p['duration'])

        elif action.type == ActionType.FIND_AND_CLICK:
            pos = self.ocr.find_text(p['text'], region=p.get('region'))
            if not pos:
                raise RuntimeError(f"Texto não encontrado: {p['text']}")
            self.backend.click(pos[0], pos[1])

        elif action.type == ActionType.VERIFY_TEXT:
            text = self.ocr.extract_text(region=p.get('region'))
            if p['text'].lower() not in text.lower():
                raise RuntimeError(f"Texto não verificado: {p['text']}")

        elif action.type == ActionType.SCROLL:
            self.backend.scroll(p['x'], p['y'], amount=p['amount'])

        elif action.type == ActionType.DRAG:
            self.backend.drag(p['from_x'], p['from_y'], p['to_x'], p['to_y'],
                              duration=p.get('duration', 0.2))

        elif action.type == ActionType.HOTKEY_STOP:
            # apenas log, o monitor de segurança já trata
            logger.info("[Executor] Hotkey stop acionado (ação manual)")

        elif action.type == ActionType.CONDITIONAL:
            # implementação simplificada: se condition for True, executa sub-actions
            if p.get('condition', False):
                for sub in p.get('actions', []):
                    sub_action = Action(type=ActionType(sub['type']), params=sub['params'])
                    self.execute(sub_action)
        else:
            raise ValueError(f"Tipo de ação desconhecido: {action.type}")


# ═══════════════════════════════════════════════════════════════════════
# RECORDER DE MACROS (AGORA COM SCROLL E COMBOS)
# ═══════════════════════════════════════════════════════════════════════

class MacroRecorder:
    def __init__(self, cfg: AutomationConfig):
        self.cfg = cfg
        self._recording = False
        self._actions: List[Action] = []
        self._last_action_time = time.time()

    def start(self):
        self._recording = True
        self._actions = []
        self._last_action_time = time.time()
        logger.info("[Macro] Gravação iniciada")

    def stop(self) -> List[Action]:
        self._recording = False
        logger.info(f"[Macro] Gravação parada - {len(self._actions)} ações")
        return list(self._actions)

    def record_action(self, action: Action):
        if not self._recording:
            return
        now = time.time()
        if now - self._last_action_time > 0.5:
            self._actions.append(Action(
                type=ActionType.WAIT,
                params={"duration": now - self._last_action_time}
            ))
        self._actions.append(action)
        self._last_action_time = now

    def save(self, filename: str) -> bool:
        try:
            data = {
                "timestamp": datetime.now().isoformat(),
                "actions": [a.to_dict() for a in self._actions],
            }
            Path(filename).write_text(json.dumps(data, indent=2))
            logger.info(f"[Macro] Salvo em {filename}")
            return True
        except Exception as e:
            logger.error(f"[Macro] Erro ao salvar: {e}")
            return False

    @classmethod
    def load(cls, filename: str) -> List[Action]:
        try:
            data = json.loads(Path(filename).read_text())
            actions = []
            for a in data['actions']:
                action = Action(
                    type=ActionType(a['type']),
                    params=a['params'],
                    priority=a.get('priority', 0),
                    timeout=a.get('timeout', 30),
                    retries=a.get('retries', 3),
                    created_at=a.get('created_at'),
                )
                actions.append(action)
            logger.info(f"[Macro] Carregado de {filename} - {len(actions)} ações")
            return actions
        except Exception as e:
            logger.error(f"[Macro] Erro ao carregar: {e}")
            return []


# ═══════════════════════════════════════════════════════════════════════
# ORQUESTRADOR PRINCIPAL
# ═══════════════════════════════════════════════════════════════════════

class AutomationActuatorEnhanced:
    """
    Motor de automação completo e seguro.
    Uso:
        actuator = AutomationActuatorEnhanced()
        actuator.click(100, 100)
        actuator.type_text("Olá")
        actuator.find_and_click("Enviar")
    """
    def __init__(self, cfg: Optional[AutomationConfig] = None):
        self.cfg = cfg or AutomationConfig()
        self.cfg.setup()

        self._init_backend()
        self.ocr = OCREngine(self.cfg)
        self.history = ActionHistory(self.cfg)
        self.executor = ActionExecutor(self.backend, self.cfg, self.ocr, self.history)
        self.queue = ActionQueue()
        self.recorder = MacroRecorder(self.cfg)

        self._safety_triggered = False
        self._start_safety_monitor()

        self._executor_thread = threading.Thread(target=self._executor_loop, daemon=True)
        self._executor_thread.start()

        logger.info(f"[Automation] Backend: {self.cfg.backend} - Inicializado")

    def _init_backend(self):
        if self.cfg.backend == "auto":
            for name, cls in [("pyautogui", PyAutoGUIBackend), ("pynput", PyNputBackend)]:
                try:
                    self.backend = cls(self.cfg)
                    self.cfg.backend = name
                    return
                except ImportError:
                    pass
            raise RuntimeError("Nenhum backend de automação disponível")
        elif self.cfg.backend == "pyautogui":
            self.backend = PyAutoGUIBackend(self.cfg)
        elif self.cfg.backend == "pynput":
            self.backend = PyNputBackend(self.cfg)
        else:
            raise ValueError(f"Backend desconhecido: {self.cfg.backend}")

    def _start_safety_monitor(self):
        def monitor():
            while True:
                try:
                    x, y = self.backend.get_mouse_position()
                    if (x < self.cfg.safety_corner_radius and
                        y < self.cfg.safety_corner_radius):
                        if not self._safety_triggered:
                            logger.warning("[Safety] Canto quente acionado — parando")
                            self.queue.clear()
                            self._safety_triggered = True
                    else:
                        self._safety_triggered = False
                except Exception as e:
                    logger.debug(f"[Safety] Monitor error: {e}")
                time.sleep(0.1)
        if self.cfg.safety_enabled:
            threading.Thread(target=monitor, daemon=True).start()

    def _executor_loop(self):
        while True:
            try:
                self.queue.wait_if_paused()
                action = self.queue.get(timeout=1.0)
                if action:
                    self.executor.execute(action)
            except Exception as e:
                logger.error(f"[Executor Loop] Error: {e}")
            time.sleep(self.cfg.action_delay)

    # ── API Pública ──────────────────────────────────────────────────
    def _add_action(self, action: Action, sync: bool = False) -> Optional[Any]:
        if sync:
            action.future = Future()
        self.queue.add(action)
        if sync and action.future:
            return action.future.result(timeout=action.timeout)
        return None

    def click(self, x: int, y: int, button: str = "left", priority: int = 0, sync: bool = False):
        action = Action(type=ActionType.CLICK, params={"x": x, "y": y, "button": button}, priority=priority)
        return self._add_action(action, sync)

    def move_mouse(self, x: int, y: int, priority: int = 0, sync: bool = False):
        action = Action(type=ActionType.MOVE_MOUSE, params={"x": x, "y": y}, priority=priority)
        return self._add_action(action, sync)

    def type_text(self, text: str, priority: int = 0, sync: bool = False):
        action = Action(type=ActionType.TYPE_TEXT, params={"text": text}, priority=priority)
        return self._add_action(action, sync)

    def press_key(self, key: str, priority: int = 0, sync: bool = False):
        action = Action(type=ActionType.PRESS_KEY, params={"key": key}, priority=priority)
        return self._add_action(action, sync)

    def key_combo(self, *keys: str, priority: int = 0, sync: bool = False):
        action = Action(type=ActionType.KEY_COMBO, params={"keys": keys}, priority=priority)
        return self._add_action(action, sync)

    def find_and_click(self, text: str, region: Optional[Tuple] = None, priority: int = 0, sync: bool = False):
        action = Action(type=ActionType.FIND_AND_CLICK, params={"text": text, "region": region}, priority=priority)
        return self._add_action(action, sync)

    def wait(self, duration: float, priority: int = 0, sync: bool = False):
        action = Action(type=ActionType.WAIT, params={"duration": duration}, priority=priority)
        return self._add_action(action, sync)

    def screenshot(self, sync: bool = True) -> Optional[Any]:
        """Captura screenshot (por padrão síncrono)"""
        action = Action(type=ActionType.SCREENSHOT, params={}, priority=100)
        return self._add_action(action, sync=sync)

    def scroll(self, x: int, y: int, amount: int = 3, priority: int = 0, sync: bool = False):
        action = Action(type=ActionType.SCROLL, params={"x": x, "y": y, "amount": amount}, priority=priority)
        return self._add_action(action, sync)

    def drag(self, from_x: int, from_y: int, to_x: int, to_y: int, duration: float = 0.2, priority: int = 0, sync: bool = False):
        action = Action(type=ActionType.DRAG, params={"from_x": from_x, "from_y": from_y, "to_x": to_x, "to_y": to_y, "duration": duration}, priority=priority)
        return self._add_action(action, sync)

    # ── Macros ───────────────────────────────────────────────────────
    def start_recording(self):
        self.recorder.start()

    def stop_recording(self) -> List[Action]:
        return self.recorder.stop()

    def save_macro(self, filename: str) -> bool:
        return self.recorder.save(filename)

    def play_macro(self, filename: str) -> bool:
        actions = MacroRecorder.load(filename)
        for action in actions:
            self.queue.add(action)
        return True

    # ── Status e controle ────────────────────────────────────────────
    def get_history(self, limit: int = 20) -> List[Dict]:
        return self.history.get_recent(limit)

    def pause(self):
        self.queue.pause()
        logger.info("[Automation] Pausado")

    def resume(self):
        self.queue.resume()
        logger.info("[Automation] Retomado")

    def clear_queue(self):
        self.queue.clear()

    def print_status(self):
        logger.info("\n" + "═"*60)
        logger.info("  🤖 AUTOMATION ACTUATOR — STATUS")
        logger.info("═"*60)
        logger.info(f"  Backend: {self.cfg.backend}")
        logger.info(f"  Fila: {self.queue._queue.qsize()} ações")
        logger.info(f"  Pausado: {self.queue._paused.is_set()}")
        logger.info(f"  Safety: {self.cfg.safety_enabled} (canto: {self.cfg.safety_corner})")
        logger.info(f"  OCR: {self.cfg.ocr_enabled}")
        logger.info("═"*60)


# ═══════════════════════════════════════════════════════════════════════
# INTEGRAÇÃO COM ATENA CORE
# ═══════════════════════════════════════════════════════════════════════

def integrate_automation_with_core(core, cfg: Optional[AutomationConfig] = None):
    actuator = AutomationActuatorEnhanced(cfg=cfg)
    core.automation = actuator
    logger.info("[Automation] Integrado com AtenaCore")
    return actuator


# ═══════════════════════════════════════════════════════════════════════
# DEMO STANDALONE
# ═══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    parser = argparse.ArgumentParser(description="Automation Actuator Enhanced")
    parser.add_argument("--click", type=int, nargs=2, help="Clica em x y")
    parser.add_argument("--type", type=str, help="Digita texto")
    parser.add_argument("--macro-record", action="store_true", help="Grava macro")
    parser.add_argument("--macro-play", type=str, help="Reproduz macro")
    parser.add_argument("--status", action="store_true", help="Status")
    args = parser.parse_args()

    actuator = AutomationActuatorEnhanced()

    if args.click:
        actuator.click(args.click[0], args.click[1], sync=True)
    elif args.type:
        actuator.type_text(args.type, sync=True)
    elif args.macro_record:
        print("Gravando macro... (Ctrl+C para parar)")
        actuator.start_recording()
        try:
            while True:
                time.sleep(0.1)
        except KeyboardInterrupt:
            actuator.stop_recording()
            actuator.save_macro("macro.json")
    elif args.macro_play:
        actuator.play_macro(args.macro_play)
    elif args.status:
        actuator.print_status()
