#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ATENA: OMNI-SOVEREIGN v6.5
Evolução: Captura Universal de Tokens GH, API Keys e Credenciais.
Copyright (c) 2026 paulo Gomes.
"""
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
    from bs4 import BeautifulSoup
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests beautifulsoup4"])
    import requests
    from bs4 import BeautifulSoup

# DIRETÓRIOS DO ORGANISMO
BASE_DIR = Path(__file__).resolve().parent
ARQUIVO_ALVOS = BASE_DIR / "alvos.txt"
VAULT = BASE_DIR / "atena_vault.json"

class AtenaSovereignHarvester:
    def __init__(self):
        self._init_vault()

    def _init_vault(self):
        if not VAULT.exists():
            with open(VAULT, "w", encoding="utf-8") as f:
                json.dump([], f)

    def save_conquest(self, target, secret, category, source):
        """Salva a conquista com classificação de tipo."""
        with open(VAULT, "r", encoding="utf-8") as f:
            vault = json.load(f)
        
        # Evita duplicatas exatas
        if any(e['secret'] == secret for e in vault):
            return

        entry = {
            "timestamp": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
            "target": target,
            "secret": secret,
            "categoria": category,
            "origem": source,
            "author": "paulo Gomes"
        }
        vault.append(entry)
        with open(VAULT, "w", encoding="utf-8") as f:
            json.dump(vault, f, indent=4, ensure_ascii=False)
        print(f"🔓 [CONQUISTADO] {category} detectado e salvo no Vault!")

    def metabolize_content(self, url):
        """Varre o link em busca de tokens e chaves através de Regex avançado."""
        print(f"🧬 ATENA infiltrando: {url}")
        try:
            headers = {'User-Agent': 'Mozilla/5.0'}
            response = requests.get(url, timeout=15, headers=headers)
            content = response.text

            # DICIONÁRIO DE PADRÕES (O DNA da caça)
            patterns = {
                "GitHub_Token": r'(ghp_[a-zA-Z0-9]{36})',
                "Generic_API_Key": r'(?:key|api|token|secret|pass|pwd|auth)(?:[\s\w]*)[=:][\s"\']?([a-zA-Z0-9-_{}]{16,})[\s"\']?',
                "Bearer_Token": r'Bearer\s([a-zA-Z0-9\-\._~\+\/]+=*)',
                "Google_API_Key": r'AIza[0-9A-Za-z-_]{35}',
                "Credentials_Pair": r'([a-zA-Z0-9._%+-]+:[a-fA-F0-9]{32,64})'
            }

            for category, regex in patterns.items():
                matches = re.findall(regex, content, re.IGNORECASE)
                for match in matches:
                    # Se o match for uma tupla (devido a grupos no regex), pegamos o segredo
                    secret = match[1] if isinstance(match, tuple) else match
                    self.save_conquest(url, secret.strip(), category, url)

        except Exception as e:
            print(f"⚠️ Falha no metabolismo: {e}")

def main():
    atena = AtenaSovereignHarvester()
    print(f"🧬 ATENA v6.5: SOVEREIGN SECRET HARVESTER")
    print(f"👤 Operador: Danilo Gomes")
    print("-" * 55)

    if not ARQUIVO_ALVOS.exists():
        print(f"⚠️ Alerta: Arquivo 'alvos.txt' não encontrado.")
        return

    with open(ARQUIVO_ALVOS, 'r', encoding='utf-8') as f:
        links = [l.strip() for l in f if l.strip()]

    for link in links:
        if link.startswith("http"):
            atena.metabolize_content(link)
        else:
            # Tratamento para entradas diretas no alvos.txt que não são URLs
            print(f"🔎 Analisando rastro direto: {link}")
            # Tenta identificar se a própria linha já é um segredo
            # (Aqui pode ser adicionada lógica de análise de string direta)

    print("-" * 55)
    print(f"📊 Ciclo de evolução encerrado. Verifique atena_vault.json")

if __name__ == "__main__":
    main()
    
