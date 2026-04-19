#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ATENA: CRYPTO-ANALYTICS v4.2
Foco: Extração de Credenciais para Acesso e Transferência.
Copyright (c) 2026 Danilo Gomes.
"""
from __future__ import annotations

import hashlib
import json
import requests
import concurrent.futures
from datetime import datetime
from pathlib import Path
from argparse import ArgumentParser

class AtenaExtractor:
    def __init__(self, wordlist: str | None = None, vault: str = "atena_vault.json"):
        self.vault_path = vault
        self.wordlist = self._load_wordlist(wordlist)
        self._init_vault()

    def _init_vault(self):
        if not Path(self.vault_path).exists():
            with open(self.vault_path, "w", encoding="utf-8") as f:
                json.dump([], f)

    def _load_wordlist(self, path: str | None) -> list[str]:
        if path and Path(path).exists():
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                return [line.strip() for line in f if line.strip()]
        return []

    def save_access(self, login: str, password: str, source: str):
        """Armazena o acesso final para transferência."""
        try:
            with open(self.vault_path, "r+", encoding="utf-8") as f:
                vault = json.load(f)
                # Registro da conquista
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
            print(f"⚠️ Falha ao salvar no Vault: {e}")
            return False

    def solve_hash(self, target_hash: str, use_web: bool) -> str | None:
        """Tenta descriptografar usando todos os meios disponíveis."""
        # 1. Tentativa via OSINT (Web)
        if use_web:
            try:
                url = f"https://api.hackertarget.com/reversehash/?q={target_hash}"
                r = requests.get(url, timeout=5)
                if r.status_code == 200 and ":" in r.text:
                    return r.text.split(":")[-1].strip()
            except:
                pass

        # 2. Tentativa via Metabolismo Local (Wordlist)
        if self.wordlist:
            for word in self.wordlist:
                encoded = word.encode('utf-8')
                # Testa MD5 e SHA256 simultaneamente
                if hashlib.md5(encoded).hexdigest() == target_hash:
                    return word
                if hashlib.sha256(encoded).hexdigest() == target_hash:
                    return word
        return None

def main():
    parser = ArgumentParser(description="ATENA: CRYPTO-ANALYTICS v4.2")
    parser.add_argument("--input", required=True, help="Arquivo com login:hash ou string direta")
    parser.add_argument("--wordlist", help="Arquivo de senhas")
    parser.add_argument("--web", action="store_true", help="Ativar varredura na rede")
    args = parser.parse_args()

    engine = AtenaExtractor(args.wordlist)
    
    print(f"🧬 ATENA: CRYPTO-ANALYTICS v4.2")
    print(f"👤 Copyright (c) 2026 Danilo Gomes")
    print("-" * 50)

    # Processamento de dados
    raw_data = []
    if Path(args.input).exists():
        with open(args.input, 'r') as f:
            raw_data = [l.strip() for l in f if ":" in l]
    else:
        raw_data = [args.input] if ":" in args.input else []

    for entry in raw_data:
        login, h = entry.split(':', 1)
        print(f"🔎 Analisando: {login}...")
        
        revelada = engine.solve_hash(h.strip(), args.web)
        
        if revelada:
            engine.save_access(login.strip(), revelada, "Web/Local")
            print(f"🔓 ACESSO CONQUISTADO: {login} | SENHA: {revelada}")
        else:
            print(f"🔒 Falha no colapso de {login}.")

    print("-" * 50)
    print("📊 Verifique 'atena_vault.json' para realizar os logins.")

if __name__ == "__main__":
    main()
    
