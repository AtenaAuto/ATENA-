#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ATENA: CRYPTO-ANALYTICS v4.2
Foco: Extração Automática de Credenciais.
Copyright (c) 2026 .
"""
import hashlib
import json
import requests
import os
import sys
from datetime import datetime
from pathlib import Path

# ==========================================================
# CONFIGURAÇÕES DA ATENA (Caminhos Inteligentes)
# ==========================================================
# Obtém o caminho da pasta onde o script está (modules/)
BASE_DIR = Path(__file__).resolve().parent

# Define os arquivos baseados na localização do script
ARQUIVO_ALVOS = BASE_DIR / "alvos.txt"
WORDLIST = BASE_DIR / "rockyou.txt"
VAULT = BASE_DIR / "atena_vault.json"

USAR_WEB = True                  # Ativa varredura na internet
# ==========================================================

class AtenaExtractor:
    def __init__(self):
        self.wordlist = self._load_wordlist(WORDLIST)
        self._init_vault()

    def _init_vault(self):
        """Garante que o Vault exista na pasta do módulo."""
        if not VAULT.exists():
            with open(VAULT, "w", encoding="utf-8") as f:
                json.dump([], f)

    def _load_wordlist(self, path):
        """Carrega a lista de senhas para o metabolismo local."""
        if path and Path(path).exists():
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                return [line.strip() for line in f if line.strip()]
        return []

    def save_access(self, login, password, source):
        """Salva o login e a senha descriptografada para transferência."""
        try:
            vault_data = []
            if VAULT.exists():
                with open(VAULT, "r", encoding="utf-8") as f:
                    vault_data = json.load(f)
            
            # Evita duplicatas de acessos já conquistados
            if any(e['login'] == login and e['password'] == password for e in vault_data):
                return False

            entry = {
                "data": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                "login": login,
                "password": password,
                "origem": source,
                "status": "PRONTO_PARA_TRANSFERENCIA",
                "author": "Danilo Gomes"
            }
            vault_data.append(entry)
            
            with open(VAULT, "w", encoding="utf-8") as f:
                json.dump(vault_data, f, indent=4, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"⚠️ Erro ao salvar conquista: {e}")
            return False

    def solve_hash(self, target_hash):
        """Tenta colapsar a hash via Web ou Local."""
        # 1. Varredura Web (OSINT)
        if USAR_WEB:
            try:
                # Consulta APIs de inteligência de rede
                url = f"https://api.hackertarget.com/reversehash/?q={target_hash}"
                r = requests.get(url, timeout=7)
                if r.status_code == 200 and ":" in r.text:
                    return r.text.split(":")[-1].strip()
            except:
                pass

        # 2. Metabolismo Local (Processamento de Wordlist)
        if self.wordlist:
            for word in self.wordlist:
                encoded = word.encode('utf-8')
                # MD5 (32 chars)
                if len(target_hash) == 32:
                    if hashlib.md5(encoded).hexdigest() == target_hash: 
                        return word
                # SHA256 (64 chars)
                elif len(target_hash) == 64:
                    if hashlib.sha256(encoded).hexdigest() == target_hash: 
                        return word
        return None

def main():
    engine = AtenaExtractor()
    
    print(f"🧬 ATENA: CRYPTO-ANALYTICS v4.2 [ATIVO]")
    print(f"👤 Copyright (c) 2026 Danilo Gomes")
    print(f"📂 Diretório: {BASE_DIR}")
    print("-" * 55)

    # Verifica se o arquivo de alvos existe na pasta modules/
    if not ARQUIVO_ALVOS.exists():
        print(f"❌ Erro: O arquivo 'alvos.txt' não está em: {ARQUIVO_ALVOS}")
        print(f"Dica: Coloque o arquivo dentro da pasta 'modules'.")
        return

    with open(ARQUIVO_ALVOS, 'r', encoding='utf-8') as f:
        linhas = [l.strip() for l in f if ":" in l]

    if not linhas:
        print("ℹ️ Nenhuma credencial encontrada no formato 'login:hash' em alvos.txt")
        return

    print(f"🔎 Processando {len(linhas)} alvos...")

    for entry in linhas:
        try:
            login, h = entry.split(':', 1)
            login = login.strip()
            h = h.strip()
            
            print(f"📡 Tentando colapso: {login}...")
            
            revelada = engine.solve_hash(h)
            
            if revelada:
                engine.save_access(login, revelada, "Rede/Local")
                print(f"🔓 CONQUISTADO: {login} | SENHA: {revelada}")
            else:
                print(f"🔒 Falha no colapso de: {login}")
        except Exception as e:
            print(f"⚠️ Erro ao processar linha '{entry}': {e}")

    print("-" * 55)
    print(f"📊 Fim do Ciclo. Acessos prontos em: {VAULT.name}")

if __name__ == "__main__":
    main()
    
