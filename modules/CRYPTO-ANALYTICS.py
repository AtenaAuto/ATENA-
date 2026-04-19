#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ATENA: CRYPTO-ANALYTICS v4.2
Foco: Extração Automática de Credenciais.
Copyright (c) 2026 Danilo Gomes.
"""
import hashlib
import json
import requests
import os
from datetime import datetime
from pathlib import Path

# ==========================================================
# CONFIGURAÇÕES DA ATENA (Edite aqui se necessário)
# ==========================================================
ARQUIVO_ALVOS = "alvos.txt"      # Nome do arquivo com login:hash
USAR_WEB = True                  # Ativa varredura na internet
WORDLIST = "rockyou.txt"         # Nome da sua lista de senhas
VAULT = "atena_vault.json"       # Onde os acessos serão salvos
# ==========================================================

class AtenaExtractor:
    def __init__(self):
        self.wordlist = self._load_wordlist(WORDLIST)
        self._init_vault()

    def _init_vault(self):
        if not Path(VAULT).exists():
            with open(VAULT, "w", encoding="utf-8") as f:
                json.dump([], f)

    def _load_wordlist(self, path):
        if path and Path(path).exists():
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                return [line.strip() for line in f if line.strip()]
        return []

    def save_access(self, login, password, source):
        try:
            with open(VAULT, "r+", encoding="utf-8") as f:
                vault = json.load(f)
                entry = {
                    "data": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                    "login": login,
                    "password": password,
                    "origem": source,
                    "status": "PRONTO_PARA_TRANSFERENCIA",
                    "author": "Danilo Gomes"
                }
                vault.append(entry)
                f.seek(0)
                json.dump(vault, f, indent=4, ensure_ascii=False)
                f.truncate()
            return True
        except Exception as e:
            print(f"⚠️ Erro ao salvar: {e}")
            return False

    def solve_hash(self, target_hash):
        # 1. Varredura Web (OSINT)
        if USAR_WEB:
            try:
                url = f"https://api.hackertarget.com/reversehash/?q={target_hash}"
                r = requests.get(url, timeout=5)
                if r.status_code == 200 and ":" in r.text:
                    return r.text.split(":")[-1].strip()
            except:
                pass

        # 2. Metabolismo Local (Wordlist)
        if self.wordlist:
            for word in self.wordlist:
                encoded = word.encode('utf-8')
                if hashlib.md5(encoded).hexdigest() == target_hash: return word
                if hashlib.sha256(encoded).hexdigest() == target_hash: return word
        return None

def main():
    engine = AtenaExtractor()
    
    print(f"🧬 ATENA: CRYPTO-ANALYTICS v4.2 [ATIVO]")
    print(f"👤 Copyright (c) 2026 Danilo Gomes")
    print("-" * 50)

    # Verifica se o arquivo de alvos existe
    if not Path(ARQUIVO_ALVOS).exists():
        print(f"❌ Erro: O arquivo '{ARQUIVO_ALVOS}' não foi encontrado.")
        return

    with open(ARQUIVO_ALVOS, 'r') as f:
        linhas = [l.strip() for l in f if ":" in l]

    for entry in linhas:
        login, h = entry.split(':', 1)
        h = h.strip()
        print(f"🔎 Colapsando: {login}...")
        
        revelada = engine.solve_hash(h)
        
        if revelada:
            engine.save_access(login.strip(), revelada, "Rede/Local")
            print(f"🔓 CONQUISTADO: {login} | SENHA: {revelada}")
        else:
            print(f"🔒 Falha no colapso de {login}.")

    print("-" * 50)
    print(f"📊 Fim do Ciclo. Acessos registrados em: {VAULT}")

if __name__ == "__main__":
    main()
    
