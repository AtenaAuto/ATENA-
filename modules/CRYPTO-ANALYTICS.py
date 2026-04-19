#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ATENA: CRYPTO-ANALYTICS v4.2
Extração de Credenciais e Persistência de Acesso.
Copyright (c) 2026 Danilo Gomes.
"""
from __future__ import annotations

import hashlib
import json
import re
import requests
import concurrent.futures
from datetime import datetime
from pathlib import Path
from argparse import ArgumentParser

# Padrões para identificar credenciais em textos brutos
EMAIL_RE = re.compile(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+')

class AtenaCredentialEngine:
    def __init__(self, wordlist_path: str | None = None, vault_path: str = "atena_vault.json"):
        self.vault_path = vault_path
        self.wordlist = self._load_wordlist(wordlist_path)
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

    def save_access(self, login: str, plain_password: str, htype: str, source: str):
        """Salva o acesso completo (Login + Senha) no Vault."""
        try:
            with open(self.vault_path, "r+", encoding="utf-8") as f:
                vault = json.load(f)
                entry = {
                    "data_conquista": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                    "login": login,
                    "password_revelada": plain_password,
                    "metodo": source,
                    "tipo_hash": htype,
                    "status": "ACESSÍVEL",
                    "autor": "Danilo Gomes"
                }
                vault.append(entry)
                f.seek(0)
                json.dump(vault, f, indent=4, ensure_ascii=False)
                f.truncate()
            return True
        except Exception as e:
            print(f"⚠️ Erro ao salvar acesso: {e}")
            return False

    def check_web(self, target_hash: str) -> str | None:
        try:
            url = f"https://api.hackertarget.com/reversehash/?q={target_hash}"
            response = requests.get(url, timeout=7)
            if response.status_code == 200 and ":" in response.text:
                return response.text.split(":")[-1].strip()
        except:
            pass
        return None

    def check_local(self, target_hash: str) -> tuple[str, str] | None:
        """Tenta MD5 e SHA256 localmente."""
        for word in self.wordlist:
            encoded = word.encode('utf-8')
            if hashlib.md5(encoded).hexdigest() == target_hash:
                return (word, "md5")
            if hashlib.sha256(encoded).hexdigest() == target_hash:
                return (word, "sha256")
        return None

def process_credential(raw_data: str, engine: AtenaCredentialEngine, use_web: bool):
    """
    Analisa uma linha de dados bruta (ex: email:hash) 
    e tenta extrair o login e a senha.
    """
    # Tenta separar login de hash (formato comum em leaks)
    parts = raw_data.split(':')
    if len(parts) < 2:
        return None
    
    login = parts[0].strip()
    target_hash = parts[1].strip()
    
    plain = None
    source = None
    htype = "unknown"

    # 1. Tentar Web
    if use_web:
        plain = engine.check_web(target_hash)
        if plain:
            source = "Scanner_Web"
            # Identificação básica de tipo pela extensão
            htype = "md5" if len(target_hash) == 32 else "sha256"

    # 2. Tentar Local
    if not plain and engine.wordlist:
        res = engine.check_local(target_hash)
        if res:
            plain, htype = res
            source = "BruteForce_Local"

    # SÓ SALVA SE CONSEGUIR A SENHA
    if plain:
        engine.save_access(login, plain, htype, source)
        return {"login": login, "pass": plain, "status": "SUCCESS"}
    
    return {"login": login, "status": "FAILED"}

def main():
    parser = ArgumentParser(description="ATENA: CRYPTO-ANALYTICS v4.2")
    parser.add_argument("--data", nargs="+", required=True, help="Dados no formato login:hash")
    parser.add_argument("--wordlist", help="Arquivo de senhas")
    parser.add_argument("--web", action="store_true", help="Varredura web ativa")
    args = parser.parse_args()

    engine = AtenaCredentialEngine(args.wordlist)
    
    print(f"🧬 ATENA: CRYPTO-ANALYTICS - Modo Extração de Acessos")
    print(f"👤 Operador: Danilo Gomes")
    print("-" * 50)

    for item in args.data:
        res = process_credential(item, engine, args.web)
        if res and res["status"] == "SUCCESS":
            print(f"🔓 ACESSO CONQUISTADO: {res['login']} | SENHA: {res['pass']}")
        else:
            print(f"🔒 Falha no colapso para: {item.split(':')[0]}")

    print("-" * 50)
    print("📊 Auditoria finalizada. Verifique 'atena_vault.json'.")

if __name__ == "__main__":
    main()
