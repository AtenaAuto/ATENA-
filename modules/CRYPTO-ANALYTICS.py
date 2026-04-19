#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ATENA: OMNI-CRYPTO v4.5
Foco: Recuperação de Credenciais via Identidade Digital e Vazamentos.
Copyright (c) 2026 .
"""
import hashlib
import json
import os
import sys
import subprocess
import re
import time
from datetime import datetime
from pathlib import Path

# AUTO-INSTALAÇÃO DE METABOLISMO
try:
    import requests
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests"])
    import requests

# CONFIGURAÇÕES
BASE_DIR = Path(__file__).resolve().parent
ARQUIVO_ALVOS = BASE_DIR / "alvos.txt"
VAULT = BASE_DIR / "atena_vault.json"

class AtenaSovereign:
    def __init__(self):
        self._init_vault()

    def _init_vault(self):
        if not VAULT.exists():
            with open(VAULT, "w", encoding="utf-8") as f:
                json.dump([], f)

    def save_access(self, login, password, source):
        try:
            with open(VAULT, "r", encoding="utf-8") as f:
                vault = json.load(f)
            if any(e['login'] == login and e['password'] == password for e in vault):
                return False
            entry = {
                "data": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                "login": login,
                "password": password,
                "origem": source,
                "status": "CONQUISTADO",
                "author": "Danilo Gomes"
            }
            vault.append(entry)
            with open(VAULT, "w", encoding="utf-8") as f:
                json.dump(vault, f, indent=4, ensure_ascii=False)
            return True
        except: return False

    def deep_hunt(self, identity):
        """
        O organismo busca por hashes vinculados ao username/email 
        em repositórios de vazamentos conhecidos.
        """
        print(f"🧬 ATENA rastreando identidade: {identity}...")
        # Simulando acesso a APIs de Leak (Ex: IntelligenceX, Leak-Lookup)
        # Aqui a ATENA busca por hashes MD5/SHA que coincidam com o rastro
        try:
            # Busca simulada em base OSINT
            url = f"https://api.hackertarget.com/reversehash/?q={identity}" 
            # Nota: Em evolução real, aqui entrariam APIs de Deep Web
            r = requests.get(url, timeout=10)
            if r.status_code == 200 and ":" in r.text:
                return r.text.split(":")[-1].strip()
        except: pass
        return None

    def extract_username(self, url):
        """Extrai o rastro digital do link."""
        parts = url.rstrip('/').split('/')
        return parts[-1] if parts else None

def main():
    atena = AtenaSovereign()
    print(f"🧬 ATENA v4.5: MÓDULO SOBERANO ATIVADO")
    print(f"👤 Operador: Danilo Gomes")
    print("-" * 55)

    if not ARQUIVO_ALVOS.exists(): return

    with open(ARQUIVO_ALVOS, 'r', encoding='utf-8') as f:
        alvos = [l.strip() for l in f if l.strip()]

    for alvo in alvos:
        if "instagram.com" in alvo or "http" in alvo:
            user = atena.extract_username(alvo)
            print(f"🛰️ Link detectado. Isolando alvo: {user}")
            
            # 1. Tentativa de Reversão por Identidade
            resultado = atena.deep_hunt(user)
            
            if resultado:
                atena.save_access(user, resultado, f"OSINT: {alvo}")
                print(f"🔓 ACESSO RECUPERADO: {user} | {resultado}")
            else:
                print(f"⚠️ Rastro insuficiente no link para colapso imediato.")
                print(f"💡 Dica: Adicione o e-mail no alvos.txt para aprofundar a busca.")

    print("-" * 55)
    print(f"📊 Evolução concluída. Resultados em: {VAULT.name}")

if __name__ == "__main__":
    main()
    
