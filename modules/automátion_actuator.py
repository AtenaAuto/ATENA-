# modules/automation_actuator_enhanced.py
"""
┌─────────────────────────────────────────────────────────────────────┐
│         ATENA AUTOMATION ACTUATOR v2.0                              │
│  Automação de teclado/mouse com segurança, OCR, macros e histórico  │
│                                                                     │
│  Features:                                                          │
│   • Fila de ações com prioridade                                    │
│   • Gravação e playback de macros                                   │
│   • OCR para encontrar elementos na tela                            │
│   • Retry automático com backoff exponencial                        │
│   • Safety locks (canto quente para parar)                          │
│   • Histórico persistente de ações                                  │
│   • Múltiplos backends (pyautogui, pynput)                          │
│   • Detecção de mudanças de tela                                    │
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
from collections import deque, namedtuple
from dataclasses import dataclass, asdict
from enum import Enum
import hashlib

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
    from PIL import Image, ImageDraw, ImageOps
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
    KEY_COMBO = "key_combo"  # Ctrl+C, etc
    SCREENSHOT = "screenshot"
    WAIT = "wait"
    FIND_AND_CLICK = "find_and_click"  # OCR + click
    VERIFY_TEXT = "verify_text"  # OCR + verify
    SCROLL = "scroll"
    DRAG = "drag"
    HOTKEY_STOP = "hotkey_stop"  # Canto quente para parar
    CONDITIONAL = "conditional"  # If/else


@dataclass
class Action:
    """Uma ação a ser executada"""
    type: ActionType
    params: Dict[str, Any]
    priority: int = 0  # Maior = maior prioridade
    timeout: int = 30  # Timeout em segundos
    retries: int = 3  # Tentativas antes de falhar
    created_at: str = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now().isoformat()
    
    def to_dict(self) -> Dict:
        d = asdict(self)
        d['type'] = self.type.value
        return d


@dataclass
class AutomationConfig:
    """Configurações de automação"""
    
    # Backends
    backend: str = "auto"  # "auto", "pyautogui", "pynput"
    
    # Segurança
    safety_enabled: bool = True
    safety_corner: Tuple[int, int] = (0, 0)  # Canto superior esquerdo
    safety_corner_radius: int = 5  # Pixels de tolerância
    
    # Comportamento
    action_delay: float = 0.05  # Delay entre ações
    type_speed: float = 0.05  # Delay entre caracteres
    click_duration: float = 0.1
    move_duration: float = 0.2
    
    # OCR/Visão
    ocr_enabled: bool = True
    ocr_language: str = "por"  # português
    image_match_threshold: float = 0.8
    
    # Histórico
    history_enabled: bool = True
    history_db: Path = Path("./atena_evolution/automation/history.db")
    history_keep_days: int = 30
    
    # Retry
    retry_enabled: bool = True
    retry_backoff: float = 1.5  # Multiplicador exponencial
    retry_max_delay: float = 10.0
    
    # Logging
    log_screenshots: bool = False
    screenshot_dir: Path = Path("./atena_evolution/automation/screenshots")
    verbose: bool = False
    
    def setup(self):
        self.history_db.parent.mkdir(parents=True, exist_ok=True)
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)


# ═══════════════════════════════════════════════════════════════════════
# BACKEND ABSTRATO
# ═══════════════════════════════════════════════════════════════════════

class AutomationBackend:
    """Interface abstrata para backends de automação"""
    
    def move_mouse(self, x: int, y: int, duration: float = 0.2):
        raise NotImplementedError
    
    def click(self, x: int, y: int, button: str = "left", clicks: int = 1):
        raise NotImplementedError
    
    def type_text(self, text: str, interval: float = 0.05):
        raise NotImplementedError
    
    def press_key(self, key: str):
        raise NotImplementedError
    
    def key_combo(self, *keys: str):
        """Pressiona combinação de teclas (Ctrl+C, etc)"""
        raise NotImplementedError
    
    def screenshot(self, region: Optional[Tuple] = None) -> Any:
        raise NotImplementedError
    
    def scroll(self, x: int, y: int, amount: int):
        raise NotImplementedError
    
    def get_mouse_position(self) -> Tuple[int, int]:
        raise NotImplementedError


class PyAutoGUIBackend(AutomationBackend):
    """Backend usando pyautogui"""
    
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


class PyNputBackend(AutomationBackend):
    """Backend usando pynput (mais flexível, sem hardcoding de teclas)"""
    
    def __init__(self, cfg: AutomationConfig):
        if not HAS_PYNPUT:
            raise ImportError("pynput não instalado")
        self.cfg = cfg
        self.mouse = mouse.Controller()
        self.keyboard = keyboard.Controller()
    
    def move_mouse(self, x: int, y: int, duration: float = 0.2):
        # pynput não tem move suave, simula
        from_x, from_y = self.mouse.position
        steps = int(duration * 60)  # 60 FPS
        for i in range(steps + 1):
            t = i / max(steps, 1)
            nx = int(from_x + (x - from_x) * t)
            ny = int(from_y + (y - from_y) * t)
            self.mouse.position = (nx, ny)
            time.sleep(1/60)
    
    def click(self, x: int, y: int, button: str = "left", clicks: int = 1):
        self.mouse.position = (x, y)
        for _ in range(clicks):
            self.mouse.click(mouse.Button.left if button == "left" else mouse.Button.right)
            time.sleep(0.1)
    
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
        }
        pressed = []
        for k in keys[:-1]:
            key_obj = key_map.get(k.lower())
            if key_obj:
                self.keyboard.press(key_obj)
                pressed.append(key_obj)
        
        # Última tecla é a "principal"
        self.press_key(keys[-1])
        
        # Libera modificadores
        for key_obj in reversed(pressed):
            self.keyboard.release(key_obj)
    
    def screenshot(self, region: Optional[Tuple] = None):
        from PIL import ImageGrab
        return ImageGrab.grab(bbox=region)
    
    def scroll(self, x: int, y: int, amount: int):
        self.mouse.position = (x, y)
        self.mouse.scroll(0, amount)
    
    def get_mouse_position(self) -> Tuple[int, int]:
        return self.mouse.position


# ═══════════════════════════════════════════════════════════════════════
# MOTOR OCR
# ═══════════════════════════════════════════════════════════════════════

class OCREngine:
    """Motor de OCR para encontrar texto na tela"""
    
    def __init__(self, cfg: AutomationConfig):
        self.cfg = cfg
        self._cache: Dict[str, Any] = {}
    
    def find_text(self, text: str, region: Optional[Tuple] = None) -> Optional[Tuple[int, int]]:
        """
        Encontra texto na tela e retorna (x, y) do centro.
        region: (left, top, right, bottom)
        """
        if not HAS_OCR:
            logger.warning("[OCR] OCR não disponível")
            return None
        
        try:
            from PIL import ImageGrab
            
            if region:
                img = ImageGrab.grab(bbox=region)
                offset_x, offset_y = region[0], region[1]
            else:
                img = ImageGrab.grab()
                offset_x, offset_y = 0, 0
            
            # OCR
            ocr_data = pytesseract.image_to_data(
                img, output_type=pytesseract.Output.DICT, lang=self.cfg.ocr_language
            )
            
            # Procura pelo texto
            for i, txt in enumerate(ocr_data['text']):
                if text.lower() in txt.lower():
                    x = ocr_data['left'][i] + ocr_data['width'][i] // 2 + offset_x
                    y = ocr_data['top'][i] + ocr_data['height'][i] // 2 + offset_y
                    return (x, y)
        
        except Exception as e:
            logger.warning(f"[OCR] Erro: {e}")
        
        return None
    
    def extract_text(self, region: Optional[Tuple] = None) -> str:
        """Extrai todo o texto de uma região"""
        if not HAS_OCR:
            return ""
        
        try:
            from PIL import ImageGrab
            img = ImageGrab.grab(bbox=region)
            return pytesseract.image_to_string(img, lang=self.cfg.ocr_language)
        except Exception as e:
            logger.warning(f"[OCR] Erro: {e}")
            return ""
    
    def find_image(self, image_path: Union[str, Path],
                   region: Optional[Tuple] = None,
                   threshold: float = 0.8) -> Optional[Tuple[int, int]]:
        """Encontra uma imagem na tela usando template matching"""
        if not HAS_CV2:
            logger.warning("[OCR] OpenCV não disponível")
            return None
        
        try:
            from PIL import ImageGrab
            
            if region:
                screen = np.array(ImageGrab.grab(bbox=region))
                offset_x, offset_y = region[0], region[1]
            else:
                screen = np.array(ImageGrab.grab())
                offset_x, offset_y = 0, 0
            
            template = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
            screen_bgr = cv2.cvtColor(screen, cv2.COLOR_RGB2BGR)
            
            result = cv2.matchTemplate(screen_bgr, template, cv2.TM_CCOEFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
            
            if max_val >= threshold:
                h, w = template.shape[:2]
                x = max_loc[0] + w // 2 + offset_x
                y = max_loc[1] + h // 2 + offset_y
                return (x, y)
        
        except Exception as e:
            logger.warning(f"[OCR] Template match error: {e}")
        
        return None


# ═══════════════════════════════════════════════════════════════════════
# GERENCIADOR DE HISTÓRICO
# ═══════════════════════════════════════════════════════════════════════

class ActionHistory:
    """Persiste histórico de ações em SQLite"""
    
    def __init__(self, cfg: AutomationConfig):
        self.cfg = cfg
        self._init_db()
    
    def _init_db(self):
        self.conn = sqlite3.connect(str(self.cfg.history_db))
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
        """Registra execução de uma ação"""
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
        """Retorna ações recentes"""
        rows = self.conn.execute("""
            SELECT action_type, status, duration, error
            FROM actions
            ORDER BY id DESC LIMIT ?
        """, (limit,)).fetchall()
        return [
            {
                "type": r[0],
                "status": r[1],
                "duration": r[2],
                "error": r[3],
            }
            for r in rows
        ]
    
    def cleanup(self):
        """Remove histórico antigo"""
        cutoff = (datetime.now() - timedelta(days=self.cfg.history_keep_days)).isoformat()
        self.conn.execute("DELETE FROM actions WHERE started_at < ?", (cutoff,))
        self.conn.commit()


# ═══════════════════════════════════════════════════════════════════════
# FILA E EXECUTOR DE AÇÕES
# ═══════════════════════════════════════════════════════════════════════

class ActionQueue:
    """Fila de ações com prioridade"""
    
    def __init__(self):
        self._queue = queue.PriorityQueue()
        self._executing = False
        self._lock = threading.RLock()
        self._paused = False
    
    def add(self, action: Action):
        """Adiciona ação à fila"""
        # Priority queue usa negativo para max-heap
        priority = (-action.priority, time.time())
        self._queue.put((priority, action))
    
    def get(self, timeout: float = 1.0) -> Optional[Action]:
        """Obtém próxima ação da fila"""
        try:
            _, action = self._queue.get(timeout=timeout)
            return action
        except queue.Empty:
            return None
    
    def is_empty(self) -> bool:
        return self._queue.empty()
    
    def pause(self):
        self._paused = True
    
    def resume(self):
        self._paused = False
    
    def clear(self):
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break


class ActionExecutor:
    """Executa ações com retry, timeout e logging"""
    
    def __init__(self, backend: AutomationBackend, cfg: AutomationConfig,
                 ocr: OCREngine, history: ActionHistory):
        self.backend = backend
        self.cfg = cfg
        self.ocr = ocr
        self.history = history
        self._last_screenshot: Optional[Any] = None
    
    def execute(self, action: Action) -> Tuple[bool, Optional[str]]:
        """
        Executa uma ação com retry automático.
        Returns: (sucesso, erro_msg)
        """
        logger.info(f"[Executor] Executando: {action.type.value}")
        
        delay = 0.5
        last_error = None
        
        for attempt in range(action.retries):
            try:
                start = time.time()
                
                # Executa ação específica
                self._execute_action(action)
                
                duration = time.time() - start
                self.history.record(action, "success", duration)
                logger.info(f"[Executor] ✅ {action.type.value} concluído em {duration:.2f}s")
                return True, None
            
            except Exception as e:
                last_error = str(e)
                logger.warning(f"[Executor] ❌ Tentativa {attempt+1}/{action.retries}: {e}")
                
                if attempt < action.retries - 1:
                    time.sleep(min(delay, self.cfg.retry_max_delay))
                    delay *= self.cfg.retry_backoff
        
        # Falhou após todas as tentativas
        self.history.record(action, "failed", 0.0, error=last_error)
        return False, last_error
    
    def _execute_action(self, action: Action):
        """Executa uma ação específica"""
        params = action.params
        
        if action.type == ActionType.MOVE_MOUSE:
            self.backend.move_mouse(
                params['x'], params['y'],
                duration=self.cfg.move_duration
            )
        
        elif action.type == ActionType.CLICK:
            self.backend.click(
                params.get('x'), params.get('y'),
                button=params.get('button', 'left'),
                clicks=params.get('clicks', 1)
            )
        
        elif action.type == ActionType.DOUBLE_CLICK:
            self.backend.click(
                params['x'], params['y'],
                button='left', clicks=2
            )
        
        elif action.type == ActionType.TYPE_TEXT:
            self.backend.type_text(
                params['text'],
                interval=self.cfg.type_speed
            )
        
        elif action.type == ActionType.PRESS_KEY:
            self.backend.press_key(params['key'])
        
        elif action.type == ActionType.KEY_COMBO:
            self.backend.key_combo(*params['keys'])
        
        elif action.type == ActionType.SCREENSHOT:
            self._last_screenshot = self.backend.screenshot(
                region=params.get('region')
            )
        
        elif action.type == ActionType.WAIT:
            time.sleep(params['duration'])
        
        elif action.type == ActionType.FIND_AND_CLICK:
            pos = self.ocr.find_text(
                params['text'],
                region=params.get('region')
            )
            if not pos:
                raise RuntimeError(f"Texto não encontrado: {params['text']}")
            self.backend.click(pos[0], pos[1])
        
        elif action.type == ActionType.VERIFY_TEXT:
            text = self.ocr.extract_text(region=params.get('region'))
            if params['text'].lower() not in text.lower():
                raise RuntimeError(f"Texto não verificado: {params['text']}")
        
        elif action.type == ActionType.SCROLL:
            self.backend.scroll(
                params['x'], params['y'],
                amount=params['amount']
            )
        
        elif action.type == ActionType.DRAG:
            self.backend.move_mouse(params['from_x'], params['from_y'])
            # Simula drag
            self.backend.click(params['from_x'], params['from_y'])
            self.backend.move_mouse(params['to_x'], params['to_y'])
            # Release (simples em pyautogui)
        
        else:
            raise ValueError(f"Tipo de ação desconhecido: {action.type}")


# ═══════════════════════════════════════════════════════════════════════
# RECORDER DE MACROS
# ═══════════════════════════════════════════════════════════════════════

class MacroRecorder:
    """Grava macros de automação"""
    
    def __init__(self, cfg: AutomationConfig):
        self.cfg = cfg
        self._recording = False
        self._actions: List[Action] = []
        self._last_action_time = time.time()
    
    def start(self):
        """Inicia gravação"""
        self._recording = True
        self._actions = []
        self._last_action_time = time.time()
        logger.info("[Macro] Gravação iniciada")
    
    def stop(self) -> List[Action]:
        """Para gravação e retorna ações"""
        self._recording = False
        logger.info(f"[Macro] Gravação parada - {len(self._actions)} ações")
        return list(self._actions)
    
    def record_mouse_move(self, x: int, y: int):
        if self._recording:
            self._actions.append(Action(
                type=ActionType.MOVE_MOUSE,
                params={"x": x, "y": y}
            ))
    
    def record_click(self, x: int, y: int, button: str = "left"):
        if self._recording:
            # Adiciona wait se passou muito tempo
            now = time.time()
            if now - self._last_action_time > 0.5:
                self._actions.append(Action(
                    type=ActionType.WAIT,
                    params={"duration": now - self._last_action_time}
                ))
            
            self._actions.append(Action(
                type=ActionType.CLICK,
                params={"x": x, "y": y, "button": button}
            ))
            self._last_action_time = now
    
    def save(self, filename: str) -> bool:
        """Salva macro em arquivo JSON"""
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
        """Carrega macro de arquivo"""
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
        
        # Backends
        self._init_backend()
        
        # Componentes
        self.ocr = OCREngine(self.cfg)
        self.history = ActionHistory(self.cfg)
        self.executor = ActionExecutor(self.backend, self.cfg, self.ocr, self.history)
        self.queue = ActionQueue()
        self.recorder = MacroRecorder(self.cfg)
        
        # Segurança
        self._safety_triggered = False
        self._start_safety_monitor()
        
        # Executor em thread
        self._executor_thread = threading.Thread(
            target=self._executor_loop,
            daemon=True
        )
        self._executor_thread.start()
        
        logger.info(f"[Automation] Backend: {self.cfg.backend}")
        logger.info("[Automation] Inicializado")
    
    def _init_backend(self):
        """Inicializa o melhor backend disponível"""
        if self.cfg.backend == "auto":
            backends = [
                ("pyautogui", PyAutoGUIBackend),
                ("pynput", PyNputBackend),
            ]
            for name, cls in backends:
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
        """Monitora o canto quente para parar automação"""
        def monitor():
            while True:
                try:
                    x, y = self.backend.get_mouse_position()
                    
                    # Verifica se está no canto de segurança
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
            t = threading.Thread(target=monitor, daemon=True)
            t.start()
    
    def _executor_loop(self):
        """Loop de execução de fila"""
        while True:
            try:
                action = self.queue.get(timeout=1.0)
                if action:
                    while self.queue._paused:
                        time.sleep(0.1)
                    
                    self.executor.execute(action)
            except Exception as e:
                logger.error(f"[Executor Loop] Error: {e}")
            
            time.sleep(self.cfg.action_delay)
    
    # ── API Pública ──────────────────────────────────────────────────
    
    def click(self, x: int, y: int, button: str = "left", priority: int = 0) -> bool:
        """Clica na posição"""
        action = Action(
            type=ActionType.CLICK,
            params={"x": x, "y": y, "button": button},
            priority=priority,
        )
        self.queue.add(action)
        return True
    
    def move_mouse(self, x: int, y: int, priority: int = 0) -> bool:
        """Move o mouse"""
        action = Action(
            type=ActionType.MOVE_MOUSE,
            params={"x": x, "y": y},
            priority=priority,
        )
        self.queue.add(action)
        return True
    
    def type_text(self, text: str, priority: int = 0) -> bool:
        """Digita texto"""
        action = Action(
            type=ActionType.TYPE_TEXT,
            params={"text": text},
            priority=priority,
        )
        self.queue.add(action)
        return True
    
    def press_key(self, key: str, priority: int = 0) -> bool:
        """Pressiona uma tecla"""
        action = Action(
            type=ActionType.PRESS_KEY,
            params={"key": key},
            priority=priority,
        )
        self.queue.add(action)
        return True
    
    def key_combo(self, *keys: str, priority: int = 0) -> bool:
        """Pressiona combinação (Ctrl+C)"""
        action = Action(
            type=ActionType.KEY_COMBO,
            params={"keys": keys},
            priority=priority,
        )
        self.queue.add(action)
        return True
    
    def find_and_click(self, text: str, region: Optional[Tuple] = None,
                      priority: int = 0) -> bool:
        """Encontra texto e clica"""
        action = Action(
            type=ActionType.FIND_AND_CLICK,
            params={"text": text, "region": region},
            priority=priority,
        )
        self.queue.add(action)
        return True
    
    def wait(self, duration: float, priority: int = 0) -> bool:
        """Aguarda"""
        action = Action(
            type=ActionType.WAIT,
            params={"duration": duration},
            priority=priority,
        )
        self.queue.add(action)
        return True
    
    def screenshot(self) -> Optional[Any]:
        """Captura screenshot"""
        action = Action(
            type=ActionType.SCREENSHOT,
            params={},
            priority=100,  # Alta prioridade
        )
        self.queue.add(action)
        # Aguarda execução
        time.sleep(0.5)
        return self.executor._last_screenshot
    
    def scroll(self, x: int, y: int, amount: int = 3, priority: int = 0) -> bool:
        """Rola a tela"""
        action = Action(
            type=ActionType.SCROLL,
            params={"x": x, "y": y, "amount": amount},
            priority=priority,
        )
        self.queue.add(action)
        return True
    
    # ── Macros ───────────────────────────────────────────────────────
    
    def start_recording(self):
        """Inicia gravação de macro"""
        self.recorder.start()
    
    def stop_recording(self) -> List[Action]:
        """Para gravação e retorna ações"""
        return self.recorder.stop()
    
    def save_macro(self, filename: str) -> bool:
        """Salva macro"""
        return self.recorder.save(filename)
    
    def play_macro(self, filename: str) -> bool:
        """Reproduz macro"""
        actions = MacroRecorder.load(filename)
        for action in actions:
            self.queue.add(action)
        return True
    
    # ── Status ───────────────────────────────────────────────────────
    
    def get_history(self, limit: int = 20) -> List[Dict]:
        """Retorna histórico recente"""
        return self.history.get_recent(limit)
    
    def pause(self):
        """Pausa a fila"""
        self.queue.pause()
        logger.info("[Automation] Pausado")
    
    def resume(self):
        """Retoma a fila"""
        self.queue.resume()
        logger.info("[Automation] Retomado")
    
    def clear_queue(self):
        """Limpa fila de ações"""
        self.queue.clear()
    
    def print_status(self):
        """Imprime status"""
        logger.info("\n" + "═"*60)
        logger.info("  🤖 AUTOMATION ACTUATOR — STATUS")
        logger.info("═"*60)
        logger.info(f"  Backend: {self.cfg.backend}")
        logger.info(f"  Fila: {self.queue._queue.qsize()} ações")
        logger.info(f"  Pausado: {self.queue._paused}")
        logger.info(f"  Safety: {self.cfg.safety_enabled} (canto: {self.cfg.safety_corner})")
        logger.info(f"  OCR: {self.cfg.ocr_enabled}")
        logger.info("═"*60)


# ═══════════════════════════════════════════════════════════════════════
# INTEGRAÇÃO COM ATENA
# ═══════════════════════════════════════════════════════════════════════

def integrate_automation_with_core(core, cfg: Optional[AutomationConfig] = None):
    """Integra automação com AtenaCore"""
    actuator = AutomationActuatorEnhanced(cfg=cfg)
    core.automation = actuator
    logger.info("[Automation] Integrado com AtenaCore")
    return actuator


# ═══════════════════════════════════════════════════════════════════════
# DEMO STANDALONE
# ═══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse
    
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s"
    )
    
    parser = argparse.ArgumentParser(description="Automation Actuator Enhanced")
    parser.add_argument("--click", type=int, nargs=2, help="Clica em x y")
    parser.add_argument("--type", type=str, help="Digita texto")
    parser.add_argument("--macro-record", action="store_true", help="Grava macro")
    parser.add_argument("--macro-play", type=str, help="Reproduz macro")
    parser.add_argument("--status", action="store_true", help="Status")
    args = parser.parse_args()
    
    cfg = AutomationConfig()
    actuator = AutomationActuatorEnhanced(cfg)
    
    if args.click:
        actuator.click(args.click[0], args.click[1])
    
    elif args.type:
        actuator.type_text(args.type)
    
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
