# modules/voice.py
"""
Módulo de voz para Atena Neural v3.1
Síntese de fala e reconhecimento de voz (opcional)
"""

import threading
import queue
import sys

try:
    import pyttsx3
    TTS_AVAILABLE = True
except ImportError:
    TTS_AVAILABLE = False
    pyttsx3 = None

try:
    import speech_recognition as sr
    SR_AVAILABLE = True
except ImportError:
    SR_AVAILABLE = False
    sr = None

class AtenaVoice:
    """Gerencia síntese e reconhecimento de voz para a Atena."""

    def __init__(self):
        self._tts_engine = None
        self._speech_queue = queue.Queue()
        self._listening = False
        self._rec_thread = None

        if TTS_AVAILABLE:
            self._init_tts()

    def _init_tts(self):
        """Inicializa o motor de síntese de fala."""
        try:
            self._tts_engine = pyttsx3.init()
            # Ajustes opcionais: velocidade, volume, voz
            rate = self._tts_engine.getProperty('rate')
            self._tts_engine.setProperty('rate', rate - 30)  # um pouco mais lento
            volume = self._tts_engine.getProperty('volume')
            self._tts_engine.setProperty('volume', volume)
        except Exception as e:
            print(f"[Voz] Erro ao inicializar TTS: {e}")
            self._tts_engine = None

    def speak(self, text, wait=False):
        """
        Fala o texto.
        Se wait=True, bloqueia até terminar.
        Caso contrário, executa em background.
        """
        if not TTS_AVAILABLE or self._tts_engine is None:
            print(f"[Voz] TTS não disponível. Texto: {text}")
            return

        def _speak():
            try:
                self._tts_engine.say(text)
                self._tts_engine.runAndWait()
            except Exception as e:
                print(f"[Voz] Erro ao falar: {e}")

        if wait:
            _speak()
        else:
            t = threading.Thread(target=_speak, daemon=True)
            t.start()

    def listen(self, timeout=3, phrase_limit=5):
        """
        Escuta um comando de voz e retorna o texto reconhecido.
        Requer speech_recognition e microfone.
        """
        if not SR_AVAILABLE:
            print("[Voz] Reconhecimento de voz não disponível.")
            return None
        recognizer = sr.Recognizer()
        with sr.Microphone() as source:
            print("[Voz] Ouvindo...")
            recognizer.adjust_for_ambient_noise(source, duration=1)
            try:
                audio = recognizer.listen(source, timeout=timeout, phrase_time_limit=phrase_limit)
            except sr.WaitTimeoutError:
                print("[Voz] Tempo esgotado.")
                return None
            except Exception as e:
                print(f"[Voz] Erro ao capturar áudio: {e}")
                return None
        try:
            # Usa Google Web Speech API (requer internet)
            text = recognizer.recognize_google(audio, language="pt-BR")
            print(f"[Voz] Reconhecido: {text}")
            return text.lower()
        except sr.UnknownValueError:
            print("[Voz] Não entendi.")
            return None
        except sr.RequestError as e:
            print(f"[Voz] Erro de requisição: {e}")
            return None
        except Exception as e:
            print(f"[Voz] Erro: {e}")
            return None

    def start_background_listening(self, callback):
        """
        Inicia uma thread que fica ouvindo continuamente.
        Cada frase reconhecida é passada para callback(texto).
        """
        if not SR_AVAILABLE:
            print("[Voz] Reconhecimento de voz não disponível.")
            return False
        if self._listening:
            return False
        self._listening = True
        def _listen_loop():
            while self._listening:
                text = self.listen(timeout=5, phrase_limit=5)
                if text and callback:
                    try:
                        callback(text)
                    except Exception as e:
                        print(f"[Voz] Erro no callback: {e}")
        self._rec_thread = threading.Thread(target=_listen_loop, daemon=True)
        self._rec_thread.start()
        return True

    def stop_background_listening(self):
        self._listening = False
        if self._rec_thread:
            self._rec_thread.join(timeout=2)

# Exemplo de integração com Atena
if __name__ == "__main__":
    voice = AtenaVoice()
    voice.speak("Olá, eu sou a Atena. Posso falar.")
    # Exemplo de escuta simples
    cmd = voice.listen()
    if cmd:
        voice.speak(f"Você disse: {cmd}")
