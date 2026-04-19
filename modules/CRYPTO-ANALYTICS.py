#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ATENA: OMNI-SOVEREIGN v5.0
Módulo: Classificação de Hashes e Automação de Crawling OSINT.
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

# AUTO-METABOLISMO
try:
    import requests
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests"])
    import requests

# DIRETÓRIOS
BASE_DIR = Path(__file__).resolve().parent
ARQUIVO_ALVOS = BASE_DIR / "alvos.txt"
VAULT = BASE_DIR / "atena_vault.json"

class AtenaAnalyticCore:
    def __init__(self):
        self._init_vault()

    def _init_vault(self):
        if not VAULT.exists():
            with open(VAULT, "w", encoding="utf-8") as f:
                json.dump([], f)

    def identify_hash(self, h):
        """Classifica o tipo de hash baseado no comprimento e caracteres."""
        h = h.strip()
        length = len(h)
        if not all(c in "0123456789abcdefABCDEF" for c in h):
            return "DESCONHECIDO"
        
        mapping = {32: "MD5", 40: "SHA-1", 64: "SHA-256", 128: "SHA-512"}
        return mapping.get(length, "HASH_DESCONHECIDA")

    def solve_hash(self, target_hash):
        """Tenta o colapso do hash via rede."""
        try:
            url = f"https://api.hackertarget.com/reversehash/?q={target_hash}"
            r = requests.get(url, timeout=7)
            if r.status_code == 200 and ":" in r.text:
                return r.text.split(":")[-1].strip()
        except: return None

    def auto_crawl(self, url):
        """Entra no link e busca padrões de login:hash automaticamente."""
        print(f"📡 ATENA penetrando link: {url}")
        try:
            headers = {'User-Agent': 'Mozilla/5.0'}
            r = requests.get(url, timeout=10, headers=headers)
            # Regex para capturar email/user : hash (32, 40 ou 64 chars)
            pattern = re.compile(r'([\w\.-]+@[\w\.-]+\.\w+|[\w\.-]+):([a-fA-F0-9]{32,64})')
            matches = pattern.findall(r.text)
            return matches
        except: return []

    def save_access(self, login, password, h_type, source):
        try:
            with open(VAULT, "r", encoding="utf-8") as f:
                vault = json.load(f)
            entry = {
                "data": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                "login": login,
                "password": password,
                "tipo": h_type,
                "origem": source,
                "author": "Danilo Gomes"
            }
            vault.append(entry)
            with open(VAULT, "w", encoding="utf-8") as f:
                json.dump(vault, f, indent=4, ensure_ascii=False)
            return True
        except: return False

def main():
    atena = AtenaAnalyticCore()
    print(f"🧬 ATENA v5.0: OMNI-SOVEREIGN CORE")
    print(f"👤 Danilo Gomes | Status: Soberano")
    print("-" * 55)

    if not ARQUIVO_ALVOS.exists(): return

    with open(ARQUIVO_ALVOS, 'r', encoding='utf-8') as f:
        alvos = [l.strip() for l in f if l.strip()]

    for alvo in alvos:
        # Se for um link, ela entra e extrai TUDO
        if alvo.startswith("http"):
            achados = atena.auto_crawl(alvo)
            for login, h in achados:
                h_type = atena.identify_hash(h)
                print(f"🔎 Alvo: {login} | Tipo: {h_type}")
                revelada = atena.solve_hash(h)
                if revelada:
                    atena.save_access(login, revelada, h_type, alvo)
                    print(f"🔓 CONQUISTADO: {revelada}")

        # Se for login:hash direto
        elif ":" in alvo:
            login, h = alvo.split(':', 1)
            h = h.strip()
            h_type = atena.identify_hash(h)
            print(f"🔎 Analisando {login} | Tipo: {h_type}")
            
            revelada = atena.solve_hash(h)
            if revelada:
                atena.save_access(login, revelada, h_type, "Entrada Direta")
                print(f"🔓 CONQUISTADO: {revelada}")
            else:
                print(f"🔒 Hash {h_type} resistente.")

    print("-" * 55)
    print(f"📊 Ciclo encerrado. Vault: {VAULT.name}")

if __name__ == "__main__":
    main()
