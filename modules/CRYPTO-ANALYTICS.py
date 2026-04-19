#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ATENA: CRYPTO-ANALYTICS v4.2
Organismo Digital de Auditoria e Inteligência.
Copyright (c) 2026 Danilo Gomes.
"""
from __future__ import annotations

import hashlib
import json
import re
import requests
import concurrent.futures
import os
from datetime import datetime
from pathlib import Path
from argparse import ArgumentParser

# Padrões de Identificação (RegEx)
PATTERNS = {
    "bcrypt": re.compile(r"^\$2[aby]\$\d{2}\$[./A-Za-z0-9]{53}$"),
    "argon2": re.compile(r"^\$argon2(id|i|d)\$.*"),
    "sha256": re.compile(r"^[a-fA-F0-9]{64}$"),
    "md5": re.compile(r"^[a-fA-F0-9]{32}$"),
}

class AtenaCryptoAnalytics:
    def __init__(self, wordlist_path: str | None = None, vault_path: str = "atena_vault.json"):
        self.vault_path = vault_path
        self.wordlist = self._load_wordlist(wordlist_path)
        self._init_vault()

    def _init_vault(self):
        """Garante que o banco de dados de descobertas exista."""
        if not Path(self.vault_path).exists():
            with open(self.vault_path, "w", encoding="utf-8") as f:
                json.dump([], f)

    def _load_wordlist(self, path: str | None) -> list[str]:
        if path and Path(path).exists():
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                return [line.strip() for line in f if line.strip()]
        return []

    def save_discovery(self, target_hash: str, htype: str, plain: str, source: str):
        """Salva a cripto convertida na memória persistente da ATENA."""
        try:
            with open(self.vault_path, "r+", encoding="utf-8") as f:
                vault = json.load(f)
                entry = {
                    "timestamp": datetime.now().isoformat(),
                    "hash": target_hash,
                    "type": htype,
                    "plain": plain,
                    "source": source,
                    "author": "Danilo Gomes"
                }
                vault.append(entry)
                f.seek(0)
                json.dump(vault, f, indent=4, ensure_ascii=False)
                f.truncate()
            return True
        except Exception as e:
            print(f"⚠️ Erro ao sincronizar Vault: {e}")
            return False

    def web_lookup(self, target_hash: str) -> str | None:
        """Scanner OSINT: Busca em bases de dados globais."""
        try:
            # Endpoint de inteligência para hashes MD5/SHA1/SHA256
            url = f"https://api.hackertarget.com/reversehash/?q={target_hash}"
            response = requests.get(url, timeout=7)
            if response.status_code == 200 and ":" in response.text:
                return response.text.split(":")[-1].strip()
        except:
            pass
        return None

    def local_crack(self, target_hash: str, htype: str) -> str | None:
        """Motor de comparação clássica de alta performance."""
        if htype not in ["md5", "sha256"] or not self.wordlist:
            return None

        for word in self.wordlist:
            encoded = word.encode('utf-8')
            if htype == "md5":
                if hashlib.md5(encoded).hexdigest() == target_hash:
                    return word
            elif htype == "sha256":
                if hashlib.sha256(encoded).hexdigest() == target_hash:
                    return word
        return None

def process_target(h: str, engine: AtenaCryptoAnalytics, use_web: bool):
    """Lógica de processamento individual por alvo."""
    # Identificar tipo de hash
    htype = "unknown"
    for name, pattern in PATTERNS.items():
        if pattern.match(h):
            htype = name
            break
    
    result = {"hash": h, "type": htype, "plain": None, "source": None}

    # 1. Tentar OSINT (Web)
    if use_web:
        found = engine.web_lookup(h)
        if found:
            result["plain"] = found
            result["source"] = "Scanner_Web"

    # 2. Tentar Crack Local
    if not result["plain"] and engine.wordlist:
        found = engine.local_crack(h, htype)
        if found:
            result["plain"] = found
            result["source"] = "BruteForce_Local"

    # 3. Persistência Automática
    if result["plain"]:
        engine.save_discovery(h, htype, result["plain"], result["source"])

    return result

def main():
    parser = ArgumentParser(description="ATENA: CRYPTO-ANALYTICS Core")
    parser.add_argument("--hashes", nargs="+", required=True, help="Hashes para processar")
    parser.add_argument("--wordlist", help="Caminho do arquivo de senhas")
    parser.add_argument("--web", action="store_true", help="Ativar inteligência web")
    parser.add_argument("--threads", type=int, default=4, help="Número de núcleos de processamento")
    args = parser.parse_args()

    engine = AtenaCryptoAnalytics(args.wordlist)
    
    print(f"🧬 ATENA: CRYPTO-ANALYTICS v4.2")
    print(f"👤 Author: Danilo Gomes")
    print(f"⚙️  Threads: {args.threads} | Web: {args.web}")
    print("-" * 50)

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.threads) as executor:
        futures = [executor.submit(process_target, h, engine, args.web) for h in args.hashes]
        
        for future in concurrent.futures.as_completed(futures):
            r = future.result()
            if r["plain"]:
                print(f"✅ SUCESSO: {r['hash'][:10]}... -> {r['plain']} ({r['source']})")
            else:
                print(f"❌ FALHA: {r['hash'][:10]}... (Tipo: {r['type']})")

    print("-" * 50)
    print(f"📊 Processamento concluído. Verifique 'atena_vault.json' para o log completo.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n⚠️ Interrupção detectada. Salvando estado...")
