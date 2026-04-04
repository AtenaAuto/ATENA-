#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Roteador de LLM da ATENA para seleção dinâmica de provider/modelo no terminal."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

from core.atena_local_lm import AtenaUltraBrain

try:
    from openai import OpenAI
except Exception:  # noqa: BLE001
    OpenAI = None


@dataclass
class LLMConfig:
    provider: str = "local"  # local | openai | compat
    model: str = "local-simbrain"
    base_url: Optional[str] = None


class AtenaLLMRouter:
    def __init__(self):
        self.cfg = LLMConfig()
        self._local_brain: Optional[AtenaUltraBrain] = None
        self._openai_client = None

    def list_options(self) -> list[str]:
        opts = ["local:local-simbrain (sempre disponível)"]
        if OpenAI is not None and os.getenv("OPENAI_API_KEY"):
            opts.append("openai:<model> (usa OPENAI_API_KEY)")
            opts.append("compat:<model> (usa OPENAI_API_KEY + ATENA_OPENAI_BASE_URL)")
        else:
            opts.append("openai/compat indisponível (faltando pacote openai ou OPENAI_API_KEY)")
        return opts

    def current(self) -> str:
        return f"{self.cfg.provider}:{self.cfg.model}"

    def set_backend(self, spec: str) -> tuple[bool, str]:
        if not spec:
            return False, "spec vazio"
        if ":" in spec:
            provider, model = spec.split(":", 1)
        else:
            provider, model = spec, ""
        provider = provider.strip().lower()
        model = model.strip()

        if provider == "local":
            self.cfg = LLMConfig(provider="local", model="local-simbrain")
            return True, "backend local ativado"

        if provider in {"openai", "compat"}:
            if OpenAI is None:
                return False, "pacote openai não instalado"
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                return False, "OPENAI_API_KEY não configurada"
            if not model:
                return False, "informe modelo no formato provider:modelo"
            base_url = os.getenv("ATENA_OPENAI_BASE_URL") if provider == "compat" else None
            self._openai_client = OpenAI(api_key=api_key, base_url=base_url)
            self.cfg = LLMConfig(provider=provider, model=model, base_url=base_url)
            return True, f"backend {provider} ativado com modelo {model}"

        return False, f"provider desconhecido: {provider}"

    def _get_local_brain(self) -> AtenaUltraBrain:
        if self._local_brain is None:
            self._local_brain = AtenaUltraBrain()
        return self._local_brain

    def generate(self, prompt: str, context: str = "") -> str:
        if self.cfg.provider == "local":
            return self._get_local_brain().think(prompt, context=context)

        # openai/compat
        response = self._openai_client.chat.completions.create(
            model=self.cfg.model,
            messages=[
                {"role": "system", "content": "Você é ATENA-Like, assistente técnico de terminal."},
                {"role": "user", "content": f"Contexto: {context}\n\nPrompt: {prompt}"},
            ],
            temperature=0.3,
            max_tokens=900,
        )
        return (response.choices[0].message.content or "").strip()

    def learn_from_feedback(self, prompt: str, response: str, success: bool, score: float) -> None:
        if self.cfg.provider == "local":
            self._get_local_brain().learn_from_feedback(prompt, response, success, score)
