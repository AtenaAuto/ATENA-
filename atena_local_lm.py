#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
┌─────────────────────────────────────────────────────────────────────┐
│         ATENA LOCAL LM — Modelo de Linguagem Próprio da Atena       │
│                                                                     │
│  Integração com atena_engine.py (v3.1)                             │
│                                                                     │
│  Arquitetura:                                                       │
│   1. AtenaLMConfig       — hiperparâmetros e caminhos              │
│   2. AtenaTinyTransformer — modelo PyTorch (Transformer causal)     │
│   3. AtenaLMDataset      — dataset incremental do KnowledgeBase     │
│   4. AtenaLMTrainer      — treinamento incremental por ciclo        │
│   5. AtenaLMGenerator    — geração de código (top-p, temperatura)   │
│   6. AtenaLMSelfEval     — a Atena avalia e pontua suas próprias    │
│                            gerações para criar sinal de treino      │
│   7. AtenaLMOrchestrator — orquestra tudo; integra ao AtenaCore    │
│                                                                     │
│  Dependências:                                                      │
│   - torch                (obrigatório para o modelo principal)      │
│   - transformers         (opcional — fallback para GPT-2 base)      │
│   Sem dependências: usa modelo n-grama estatístico como fallback    │
│                                                                     │
│  Como usar (drop-in no atena_engine.py):                           │
│   from atena_local_lm import AtenaLMOrchestrator                   │
│   # Em AtenaCore.__init__:                                          │
│   self.local_lm = AtenaLMOrchestrator(self)                        │
│   # Em evolve_one_cycle, após registro de episódio:                │
│   self.local_lm.on_cycle_end(self.generation, self.current_code,   │
│                               metrics, replaced)                    │
└─────────────────────────────────────────────────────────────────────┘
"""

import os
import re
import ast
import json
import math
import time
import random
import hashlib
import logging
import sqlite3
import threading
import textwrap
import pickle
import struct
from pathlib import Path
from datetime import datetime, timedelta
from typing import (
    Any, Dict, List, Optional, Tuple, Callable, Iterator
)
from collections import Counter, defaultdict, deque
from dataclasses import dataclass, field

logger = logging.getLogger("atena.lm")

# ── Detecção de backends disponíveis ─────────────────────────────────

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    from torch.utils.data import Dataset, DataLoader
    HAS_TORCH = True
    DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    logger.info(f"[AtenaLM] PyTorch disponível — device: {DEVICE}")
except ImportError:
    HAS_TORCH = False
    DEVICE = None
    logger.warning("[AtenaLM] PyTorch não encontrado — usando fallback n-grama")

try:
    from transformers import (
        GPT2LMHeadModel, GPT2Tokenizer, GPT2Config,
        TrainingArguments, Trainer, DataCollatorForLanguageModeling,
    )
    HAS_TRANSFORMERS = True
    logger.info("[AtenaLM] HuggingFace Transformers disponível")
except ImportError:
    HAS_TRANSFORMERS = False


# ═══════════════════════════════════════════════════════════════════════
# 1. CONFIGURAÇÃO
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class AtenaLMConfig:
    """Hiperparâmetros e caminhos do modelo local da Atena."""

    # Diretório base (deve ser compatível com Config.BASE_DIR do engine)
    base_dir: Path = Path("./atena_evolution/lm")

    # Estratégia de modelo
    # "tiny"        → AtenaTinyTransformer (sem deps externas além de torch)
    # "gpt2"        → GPT-2 small via transformers (requer transformers)
    # "ngram"       → Fallback estatístico, sem torch
    model_strategy: str = "auto"   # auto escolhe o melhor disponível

    # AtenaTinyTransformer
    vocab_size: int = 8192          # tokens do tokenizer de char-BPE simplificado
    embed_dim: int = 128
    num_heads: int = 4
    num_layers: int = 4
    ffn_dim: int = 512
    max_seq_len: int = 512
    dropout: float = 0.1

    # Treinamento incremental
    train_every_n_cycles: int = 5   # treina a cada N ciclos
    train_epochs_per_cycle: int = 2
    batch_size: int = 8
    learning_rate: float = 3e-4
    gradient_clip: float = 1.0
    max_train_samples: int = 2048   # max amostras por sessão de treino
    min_train_samples: int = 64     # mínimo para iniciar treino
    warmup_steps: int = 100

    # Geração
    temperature: float = 0.8
    top_p: float = 0.92
    top_k: int = 50
    max_new_tokens: int = 256
    repetition_penalty: float = 1.15

    # N-grama (fallback)
    ngram_order: int = 4
    ngram_laplace: float = 0.01

    # Self-eval
    selfeval_enabled: bool = True
    selfeval_weight: float = 0.3    # peso do sinal de auto-avaliação no treino

    # API como fonte de dados (não para geração)
    use_api_for_data: bool = True   # usa Grok/GitHub apenas para coletar exemplos

    @property
    def model_dir(self) -> Path:
        return self.base_dir / "model"

    @property
    def checkpoint_dir(self) -> Path:
        return self.base_dir / "checkpoints"

    @property
    def data_dir(self) -> Path:
        return self.base_dir / "data"

    @property
    def vocab_path(self) -> Path:
        return self.base_dir / "vocab.json"

    @property
    def ngram_path(self) -> Path:
        return self.base_dir / "ngram.pkl"

    def setup(self):
        for d in [self.base_dir, self.model_dir, self.checkpoint_dir, self.data_dir]:
            d.mkdir(parents=True, exist_ok=True)

    def resolve_strategy(self) -> str:
        if self.model_strategy != "auto":
            return self.model_strategy
        if HAS_TORCH:
            return "tiny"
        return "ngram"


# ═══════════════════════════════════════════════════════════════════════
# 2. TOKENIZER CHAR-BPE SIMPLIFICADO
# ═══════════════════════════════════════════════════════════════════════

class AtenaTokenizer:
    """
    Tokenizer leve baseado em caracteres + BPE incremental.
    Não depende de bibliotecas externas.
    """

    PAD_ID   = 0
    UNK_ID   = 1
    BOS_ID   = 2
    EOS_ID   = 3
    SPECIAL  = ["<PAD>", "<UNK>", "<BOS>", "<EOS>"]

    def __init__(self, vocab_size: int = 8192):
        self.vocab_size = vocab_size
        self.token2id: Dict[str, int] = {}
        self.id2token: Dict[int, str] = {}
        self._init_special()
        self._merges: List[Tuple[str, str]] = []   # BPE merges
        self._trained = False

    def _init_special(self):
        for i, tok in enumerate(self.SPECIAL):
            self.token2id[tok] = i
            self.id2token[i] = tok

    # ── Treinamento BPE leve ─────────────────────────────────────────

    def train(self, texts: List[str], num_merges: int = None):
        """Treina o tokenizer BPE incremental."""
        if num_merges is None:
            num_merges = self.vocab_size - 256 - len(self.SPECIAL)
        num_merges = max(0, num_merges)

        # Inicializa vocab com bytes ASCII/UTF-8
        for i in range(256):
            ch = chr(i)
            tid = len(self.token2id)
            if ch not in self.token2id:
                self.token2id[ch] = tid
                self.id2token[tid] = ch

        # Corpus como sequência de tokens de caractere
        corpus = []
        for text in texts:
            words = text.split()
            for w in words:
                chars = list(w) + ["Ġ"]   # marcador de espaço
                corpus.append(chars)

        for merge_idx in range(num_merges):
            if len(self.token2id) >= self.vocab_size:
                break
            pairs = Counter()
            for word in corpus:
                for a, b in zip(word[:-1], word[1:]):
                    pairs[(a, b)] += 1
            if not pairs:
                break
            best = max(pairs, key=pairs.get)
            if pairs[best] < 2:
                break
            new_tok = best[0] + best[1]
            if new_tok not in self.token2id:
                tid = len(self.token2id)
                self.token2id[new_tok] = tid
                self.id2token[tid] = new_tok
            self._merges.append(best)
            # Aplica merge
            new_corpus = []
            for word in corpus:
                new_word = []
                i = 0
                while i < len(word):
                    if i < len(word) - 1 and (word[i], word[i+1]) == best:
                        new_word.append(new_tok)
                        i += 2
                    else:
                        new_word.append(word[i])
                        i += 1
                new_corpus.append(new_word)
            corpus = new_corpus

        self._trained = True
        logger.info(f"[AtenaTokenizer] Vocabulário: {len(self.token2id)} tokens, "
                    f"{len(self._merges)} merges BPE")

    def encode(self, text: str, add_bos: bool = True, add_eos: bool = True) -> List[int]:
        """Codifica texto em IDs."""
        ids = []
        if add_bos:
            ids.append(self.BOS_ID)
        # Tokenização caractere a caractere com merges aplicados
        chars = list(text)
        for merge in self._merges:
            a, b = merge
            new_tok = a + b
            merged = []
            i = 0
            while i < len(chars):
                if i < len(chars) - 1 and chars[i] == a and chars[i+1] == b:
                    merged.append(new_tok)
                    i += 2
                else:
                    merged.append(chars[i])
                    i += 1
            chars = merged
        for ch in chars:
            ids.append(self.token2id.get(ch, self.UNK_ID))
        if add_eos:
            ids.append(self.EOS_ID)
        return ids

    def decode(self, ids: List[int]) -> str:
        """Decodifica IDs em texto."""
        parts = []
        for i in ids:
            if i in (self.PAD_ID, self.BOS_ID, self.EOS_ID):
                continue
            parts.append(self.id2token.get(i, "?"))
        text = "".join(parts).replace("Ġ", " ")
        return text

    def save(self, path: Path):
        data = {
            "vocab_size": self.vocab_size,
            "token2id": self.token2id,
            "merges": self._merges,
        }
        path.write_text(json.dumps(data, ensure_ascii=False))

    @classmethod
    def load(cls, path: Path) -> "AtenaTokenizer":
        data = json.loads(path.read_text())
        tok = cls(data["vocab_size"])
        tok.token2id = {k: int(v) for k, v in data["token2id"].items()}
        tok.id2token = {int(v): k for k, v in data["token2id"].items()}
        tok._merges  = [tuple(m) for m in data["merges"]]
        tok._trained = True
        return tok

    @classmethod
    def load_or_create(cls, path: Path, vocab_size: int = 8192) -> "AtenaTokenizer":
        if path.exists():
            try:
                tok = cls.load(path)
                logger.info(f"[AtenaTokenizer] Carregado de {path} ({len(tok.token2id)} tokens)")
                return tok
            except Exception as e:
                logger.warning(f"[AtenaTokenizer] Falha ao carregar: {e} — criando novo")
        tok = cls(vocab_size)
        # Bootstrap com ASCII
        for i in range(256):
            ch = chr(i)
            if ch not in tok.token2id:
                tid = len(tok.token2id)
                tok.token2id[ch] = tid
                tok.id2token[tid] = ch
        return tok


# ═══════════════════════════════════════════════════════════════════════
# 3. MODELO TINY TRANSFORMER (PyTorch)
# ═══════════════════════════════════════════════════════════════════════

if HAS_TORCH:

    class CausalSelfAttention(nn.Module):
        def __init__(self, embed_dim: int, num_heads: int,
                     max_seq_len: int, dropout: float):
            super().__init__()
            assert embed_dim % num_heads == 0
            self.num_heads = num_heads
            self.head_dim  = embed_dim // num_heads
            self.scale     = self.head_dim ** -0.5
            self.qkv  = nn.Linear(embed_dim, 3 * embed_dim, bias=False)
            self.proj = nn.Linear(embed_dim, embed_dim, bias=False)
            self.attn_drop = nn.Dropout(dropout)
            self.proj_drop = nn.Dropout(dropout)
            # Máscara causal (não é parâmetro)
            self.register_buffer(
                "mask",
                torch.tril(torch.ones(max_seq_len, max_seq_len)).unsqueeze(0).unsqueeze(0)
            )

        def forward(self, x: "torch.Tensor") -> "torch.Tensor":
            B, T, C = x.shape
            qkv = self.qkv(x).reshape(B, T, 3, self.num_heads, self.head_dim)
            qkv = qkv.permute(2, 0, 3, 1, 4)
            q, k, v = qkv[0], qkv[1], qkv[2]
            att = (q @ k.transpose(-2, -1)) * self.scale
            att = att.masked_fill(self.mask[:, :, :T, :T] == 0, float('-inf'))
            att = F.softmax(att, dim=-1)
            att = self.attn_drop(att)
            out = (att @ v).transpose(1, 2).reshape(B, T, C)
            return self.proj_drop(self.proj(out))


    class TransformerBlock(nn.Module):
        def __init__(self, embed_dim: int, num_heads: int, ffn_dim: int,
                     max_seq_len: int, dropout: float):
            super().__init__()
            self.ln1  = nn.LayerNorm(embed_dim)
            self.attn = CausalSelfAttention(embed_dim, num_heads, max_seq_len, dropout)
            self.ln2  = nn.LayerNorm(embed_dim)
            self.ffn  = nn.Sequential(
                nn.Linear(embed_dim, ffn_dim),
                nn.GELU(),
                nn.Dropout(dropout),
                nn.Linear(ffn_dim, embed_dim),
                nn.Dropout(dropout),
            )

        def forward(self, x: "torch.Tensor") -> "torch.Tensor":
            x = x + self.attn(self.ln1(x))
            x = x + self.ffn(self.ln2(x))
            return x


    class AtenaTinyTransformer(nn.Module):
        """
        Transformer causal compacto — modelo de linguagem próprio da Atena.
        ~3M parâmetros com configuração padrão (embed=128, 4 camadas).
        """

        def __init__(self, cfg: AtenaLMConfig):
            super().__init__()
            self.cfg = cfg
            self.tok_emb = nn.Embedding(cfg.vocab_size, cfg.embed_dim, padding_idx=0)
            self.pos_emb = nn.Embedding(cfg.max_seq_len, cfg.embed_dim)
            self.drop    = nn.Dropout(cfg.dropout)
            self.blocks  = nn.ModuleList([
                TransformerBlock(
                    cfg.embed_dim, cfg.num_heads, cfg.ffn_dim,
                    cfg.max_seq_len, cfg.dropout
                )
                for _ in range(cfg.num_layers)
            ])
            self.ln_f  = nn.LayerNorm(cfg.embed_dim)
            self.head  = nn.Linear(cfg.embed_dim, cfg.vocab_size, bias=False)
            # Weight tying
            self.head.weight = self.tok_emb.weight
            self.apply(self._init_weights)
            n_params = sum(p.numel() for p in self.parameters())
            logger.info(f"[AtenaTinyTransformer] {n_params/1e6:.2f}M parâmetros")

        def _init_weights(self, module):
            if isinstance(module, (nn.Linear, nn.Embedding)):
                nn.init.normal_(module.weight, mean=0.0, std=0.02)
                if isinstance(module, nn.Linear) and module.bias is not None:
                    nn.init.zeros_(module.bias)

        def forward(self, idx: "torch.Tensor",
                    targets: "Optional[torch.Tensor]" = None):
            B, T = idx.shape
            assert T <= self.cfg.max_seq_len, f"Sequência {T} > max {self.cfg.max_seq_len}"
            pos = torch.arange(T, device=idx.device).unsqueeze(0)
            x = self.drop(self.tok_emb(idx) + self.pos_emb(pos))
            for block in self.blocks:
                x = block(x)
            logits = self.head(self.ln_f(x))
            loss = None
            if targets is not None:
                loss = F.cross_entropy(
                    logits.view(-1, logits.size(-1)),
                    targets.view(-1),
                    ignore_index=0
                )
            return logits, loss

        @torch.no_grad()
        def generate(self, idx: "torch.Tensor", max_new_tokens: int,
                     temperature: float = 1.0, top_k: int = 0,
                     top_p: float = 1.0,
                     repetition_penalty: float = 1.0) -> "torch.Tensor":
            """Geração autoregressiva com top-p e penalidade de repetição."""
            self.eval()
            for _ in range(max_new_tokens):
                idx_cond = idx[:, -self.cfg.max_seq_len:]
                logits, _ = self(idx_cond)
                logits = logits[:, -1, :] / max(temperature, 1e-5)

                # Penalidade de repetição
                if repetition_penalty != 1.0:
                    for token_id in set(idx[0].tolist()):
                        logits[0, token_id] /= repetition_penalty

                # Top-k
                if top_k > 0:
                    vals, _ = torch.topk(logits, top_k)
                    logits[logits < vals[:, -1:]] = float('-inf')

                # Top-p (nucleus)
                if top_p < 1.0:
                    sorted_logits, sorted_idx = torch.sort(logits, descending=True)
                    cumprobs = torch.cumsum(F.softmax(sorted_logits, dim=-1), dim=-1)
                    remove = cumprobs - F.softmax(sorted_logits, dim=-1) > top_p
                    remove[:, 0] = False
                    sorted_logits[remove] = float('-inf')
                    logits = sorted_logits.scatter(1, sorted_idx, sorted_logits)

                probs = F.softmax(logits, dim=-1)
                next_tok = torch.multinomial(probs, num_samples=1)

                if next_tok.item() == AtenaTokenizer.EOS_ID:
                    break
                idx = torch.cat([idx, next_tok], dim=1)

            return idx

        def save(self, path: Path):
            torch.save(self.state_dict(), str(path / "model.pt"))
            # Salva config
            (path / "config.json").write_text(json.dumps({
                "vocab_size": self.cfg.vocab_size,
                "embed_dim": self.cfg.embed_dim,
                "num_heads": self.cfg.num_heads,
                "num_layers": self.cfg.num_layers,
                "ffn_dim": self.cfg.ffn_dim,
                "max_seq_len": self.cfg.max_seq_len,
                "dropout": self.cfg.dropout,
            }))
            logger.info(f"[AtenaTinyTransformer] Salvo em {path}")

        @classmethod
        def load(cls, path: Path, cfg: AtenaLMConfig) -> "AtenaTinyTransformer":
            model = cls(cfg)
            state = torch.load(str(path / "model.pt"), map_location=DEVICE)
            model.load_state_dict(state, strict=False)
            model.to(DEVICE)
            logger.info(f"[AtenaTinyTransformer] Carregado de {path}")
            return model

        @classmethod
        def load_or_create(cls, path: Path, cfg: AtenaLMConfig) -> "AtenaTinyTransformer":
            model_file = path / "model.pt"
            if model_file.exists():
                try:
                    return cls.load(path, cfg)
                except Exception as e:
                    logger.warning(f"[AtenaLM] Falha ao carregar modelo: {e} — criando novo")
            model = cls(cfg)
            model.to(DEVICE)
            return model


# ═══════════════════════════════════════════════════════════════════════
# 4. MODELO N-GRAMA (fallback sem PyTorch)
# ═══════════════════════════════════════════════════════════════════════

class AtenaNgramLM:
    """
    Modelo de linguagem baseado em n-gramas com suavização de Laplace.
    Geração de código Python por amostragem das distribuições.
    """

    def __init__(self, order: int = 4, laplace: float = 0.01):
        self.order   = order
        self.laplace = laplace
        self._counts: Dict[tuple, Counter] = defaultdict(Counter)
        self._vocab: Counter = Counter()
        self._trained = False
        self._code_templates: List[str] = []

    def train(self, texts: List[str]):
        """Treina o modelo n-grama nos textos."""
        for text in texts:
            tokens = list(text)
            self._vocab.update(tokens)
            for i in range(len(tokens) - self.order):
                ctx = tuple(tokens[i:i + self.order])
                nxt = tokens[i + self.order]
                self._counts[ctx][nxt] += 1
            # Salva templates de código bem formados
            if "def " in text and len(text) > 50:
                self._code_templates.append(text[:512])
        self._trained = True
        logger.info(f"[AtenaNgramLM] Treinado: {len(self._counts)} contextos, "
                    f"{len(self._vocab)} símbolos únicos")

    def _next_token(self, context: tuple) -> str:
        ctx = context[-self.order:]
        counts = self._counts.get(ctx, Counter())
        if not counts:
            # Recua o contexto
            for n in range(self.order - 1, 0, -1):
                shorter = context[-n:]
                counts = self._counts.get(shorter, Counter())
                if counts:
                    break
        if not counts:
            # Uniforme sobre vocabulário
            return random.choice(list(self._vocab.keys()))

        tokens = list(counts.keys())
        freqs  = [counts[t] + self.laplace for t in tokens]
        total  = sum(freqs)
        probs  = [f / total for f in freqs]
        return random.choices(tokens, weights=probs, k=1)[0]

    def generate(self, prompt: str, max_tokens: int = 200, temperature: float = 1.0) -> str:
        if not self._trained:
            return random.choice(self._code_templates) if self._code_templates else ""
        tokens = list(prompt[-self.order * 4:])
        for _ in range(max_tokens):
            ctx = tuple(tokens[-self.order:])
            nxt = self._next_token(ctx)
            tokens.append(nxt)
            if nxt == '\n' and len(tokens) > 30:
                # Verifica se chegamos a um ponto de parada natural
                recent = "".join(tokens[-20:])
                if recent.count('\n') >= 2 and tokens[-1] == '\n':
                    break
        return "".join(tokens)

    def generate_function(self, hint: str = "") -> str:
        """Tenta gerar uma função Python completa."""
        # Escolhe template e aplica variações
        if self._code_templates:
            base = random.choice(self._code_templates)
            if self._trained:
                # Usa o modelo para continuar a partir do template
                prompt = base[:min(len(base) // 2, self.order * 8)]
                return prompt + self.generate(prompt, max_tokens=150)
            return base
        return self.generate("def util_", max_tokens=150)

    def save(self, path: Path):
        data = {
            "order": self.order,
            "laplace": self.laplace,
            "counts": {str(k): dict(v) for k, v in self._counts.items()},
            "vocab": dict(self._vocab),
            "templates": self._code_templates[:50],
        }
        with open(str(path), 'wb') as f:
            pickle.dump(data, f)
        logger.info(f"[AtenaNgramLM] Salvo em {path}")

    @classmethod
    def load(cls, path: Path) -> "AtenaNgramLM":
        with open(str(path), 'rb') as f:
            data = pickle.load(f)
        m = cls(data["order"], data["laplace"])
        m._counts = defaultdict(Counter,
            {eval(k): Counter(v) for k, v in data["counts"].items()})
        m._vocab   = Counter(data["vocab"])
        m._code_templates = data.get("templates", [])
        m._trained = True
        logger.info(f"[AtenaNgramLM] Carregado de {path}")
        return m

    @classmethod
    def load_or_create(cls, path: Path, order: int = 4) -> "AtenaNgramLM":
        if path.exists():
            try:
                return cls.load(path)
            except Exception as e:
                logger.warning(f"[AtenaNgramLM] Falha ao carregar: {e}")
        return cls(order)


# ═══════════════════════════════════════════════════════════════════════
# 5. DATASET INCREMENTAL
# ═══════════════════════════════════════════════════════════════════════

class AtenaLMDataset:
    """
    Coleta e gerencia o dataset de treino a partir de:
    - KnowledgeBase (funções do GitHub)
    - Mutações bem-sucedidas (código aceito)
    - Saída da auto-avaliação (sinal de qualidade)
    """

    def __init__(self, cfg: AtenaLMConfig, db_conn: sqlite3.Connection):
        self.cfg  = cfg
        self.conn = db_conn
        self._buffer: List[str] = []      # textos brutos
        self._scored: List[Tuple[str, float]] = []   # (texto, score)
        self._lock = threading.RLock()
        self._data_file = cfg.data_dir / "corpus.jsonl"
        self._load_existing()

    def _load_existing(self):
        """Carrega corpus salvo em disco."""
        if self._data_file.exists():
            try:
                with open(self._data_file) as f:
                    for line in f:
                        obj = json.loads(line)
                        self._buffer.append(obj["text"])
                        if "score" in obj:
                            self._scored.append((obj["text"], obj["score"]))
                logger.info(f"[AtenaLMDataset] {len(self._buffer)} amostras carregadas do disco")
            except Exception as e:
                logger.warning(f"[AtenaLMDataset] Erro ao carregar corpus: {e}")

    def collect_from_kb(self, limit: int = 500):
        """Coleta funções da KnowledgeBase como dados de treino."""
        try:
            rows = self.conn.execute(
                "SELECT code FROM learned_functions "
                "ORDER BY usage_count DESC, complexity ASC LIMIT ?",
                (limit,)
            ).fetchall()
            new_texts = []
            for (code,) in rows:
                if code and len(code.strip()) > 30:
                    # Verifica sintaxe
                    try:
                        ast.parse(code)
                        new_texts.append(code.strip())
                    except Exception:
                        pass
            with self._lock:
                before = len(self._buffer)
                self._buffer.extend(new_texts)
                added = len(self._buffer) - before
            logger.info(f"[AtenaLMDataset] {added} funções coletadas do KB")
            return added
        except Exception as e:
            logger.warning(f"[AtenaLMDataset] Erro ao coletar do KB: {e}")
            return 0

    def collect_from_evolution(self, limit: int = 200):
        """Coleta código de mutações bem-sucedidas."""
        try:
            rows = self.conn.execute("""
                SELECT em.mutation, em.new_score, ep.code_snapshot
                FROM evolution_metrics em
                LEFT JOIN episodic_memory ep ON ep.generation = em.generation
                WHERE em.replaced = 1 AND ep.code_snapshot IS NOT NULL
                ORDER BY em.new_score DESC LIMIT ?
            """, (limit,)).fetchall()
            new_scored = []
            for mutation, score, snapshot in rows:
                if snapshot and len(snapshot.strip()) > 30:
                    new_scored.append((snapshot.strip(), float(score or 0)))
            with self._lock:
                self._scored.extend(new_scored)
                self._buffer.extend([t for t, _ in new_scored])
            logger.info(f"[AtenaLMDataset] {len(new_scored)} snapshots de evolução coletados")
            return len(new_scored)
        except Exception as e:
            logger.debug(f"[AtenaLMDataset] Erro ao coletar evolução: {e}")
            return 0

    def add_text(self, text: str, score: float = -1.0):
        """Adiciona um texto ao dataset."""
        if not text or len(text.strip()) < 10:
            return
        with self._lock:
            self._buffer.append(text.strip())
            if score >= 0:
                self._scored.append((text.strip(), score))

    def save_corpus(self):
        """Salva corpus em disco (formato JSONL)."""
        try:
            scored_dict = {t: s for t, s in self._scored}
            with open(self._data_file, 'w') as f:
                for text in self._buffer:
                    obj = {"text": text}
                    if text in scored_dict:
                        obj["score"] = scored_dict[text]
                    f.write(json.dumps(obj, ensure_ascii=False) + "\n")
            logger.info(f"[AtenaLMDataset] Corpus salvo: {len(self._buffer)} amostras")
        except Exception as e:
            logger.warning(f"[AtenaLMDataset] Erro ao salvar corpus: {e}")

    def get_texts(self, max_samples: int = None,
                  prefer_high_score: bool = True) -> List[str]:
        """Retorna textos para treino, priorizando os de maior score."""
        with self._lock:
            texts = list(self._buffer)

        if not texts:
            return []

        if prefer_high_score and self._scored:
            # Ordena por score e intercala com amostras aleatórias
            scored_texts = sorted(self._scored, key=lambda x: x[1], reverse=True)
            top_texts = [t for t, _ in scored_texts[:len(scored_texts) // 2]]
            rest = list(set(texts) - set(top_texts))
            random.shuffle(rest)
            texts = top_texts + rest
        else:
            random.shuffle(texts)

        limit = max_samples or len(texts)
        return texts[:limit]

    def size(self) -> int:
        return len(self._buffer)

    def stats(self) -> Dict:
        return {
            "total_samples": len(self._buffer),
            "scored_samples": len(self._scored),
            "avg_score": (
                sum(s for _, s in self._scored) / len(self._scored)
                if self._scored else 0.0
            ),
        }


# ═══════════════════════════════════════════════════════════════════════
# 6. TRAINER INCREMENTAL
# ═══════════════════════════════════════════════════════════════════════

if HAS_TORCH:
    class _TorchTextDataset(Dataset):
        """Dataset PyTorch para treino do Transformer."""
        def __init__(self, texts: List[str], tokenizer: AtenaTokenizer,
                     max_len: int, stride: int = None):
            self.samples: List[List[int]] = []
            stride = stride or max_len // 2
            for text in texts:
                ids = tokenizer.encode(text, add_bos=True, add_eos=True)
                for start in range(0, max(1, len(ids) - max_len), stride):
                    chunk = ids[start:start + max_len + 1]
                    if len(chunk) >= 4:
                        self.samples.append(chunk)

        def __len__(self):
            return len(self.samples)

        def __getitem__(self, idx):
            chunk = self.samples[idx]
            x = torch.tensor(chunk[:-1], dtype=torch.long)
            y = torch.tensor(chunk[1:],  dtype=torch.long)
            return x, y

        def collate(self, batch):
            xs, ys = zip(*batch)
            max_len = max(x.size(0) for x in xs)
            xs_pad = torch.zeros(len(xs), max_len, dtype=torch.long)
            ys_pad = torch.zeros(len(ys), max_len, dtype=torch.long)
            for i, (x, y) in enumerate(zip(xs, ys)):
                xs_pad[i, :x.size(0)] = x
                ys_pad[i, :y.size(0)] = y
            return xs_pad, ys_pad


class AtenaLMTrainer:
    """
    Treinamento incremental do modelo local da Atena.
    A cada chamada train(), ajusta o modelo com o corpus acumulado.
    """

    def __init__(self, cfg: AtenaLMConfig, tokenizer: AtenaTokenizer,
                 model, dataset: AtenaLMDataset):
        self.cfg       = cfg
        self.tokenizer = tokenizer
        self.model     = model      # AtenaTinyTransformer ou AtenaNgramLM
        self.dataset   = dataset
        self._step     = 0
        self._losses: deque = deque(maxlen=100)
        self._perplexities: deque = deque(maxlen=50)

    def train(self, cycle: int) -> Dict:
        """Executa uma sessão de treino incremental."""
        texts = self.dataset.get_texts(
            max_samples=self.cfg.max_train_samples,
            prefer_high_score=True
        )
        if len(texts) < self.cfg.min_train_samples:
            logger.info(f"[AtenaLMTrainer] Amostras insuficientes: "
                        f"{len(texts)}/{self.cfg.min_train_samples}")
            return {"skipped": True, "samples": len(texts)}

        logger.info(f"[AtenaLMTrainer] 🏋️  Treino — ciclo {cycle} | "
                    f"{len(texts)} amostras")
        t0 = time.time()

        if HAS_TORCH and isinstance(self.model, AtenaTinyTransformer):
            result = self._train_torch(texts, cycle)
        else:
            result = self._train_ngram(texts)

        result["elapsed"] = round(time.time() - t0, 2)
        result["cycle"]   = cycle
        result["samples"] = len(texts)
        logger.info(f"[AtenaLMTrainer] ✅ Treino concluído em {result['elapsed']:.1f}s — "
                    f"loss={result.get('final_loss', 'N/A')}")
        # Salva após treino
        self._save()
        return result

    def _train_torch(self, texts: List[str], cycle: int) -> Dict:
        """Treino com PyTorch."""
        torch_dataset = _TorchTextDataset(
            texts, self.tokenizer,
            self.cfg.max_seq_len,
        )
        if len(torch_dataset) == 0:
            return {"error": "dataset vazio após tokenização"}

        loader = DataLoader(
            torch_dataset,
            batch_size=self.cfg.batch_size,
            shuffle=True,
            collate_fn=torch_dataset.collate,
            num_workers=0,
        )

        self.model.train()
        optimizer = torch.optim.AdamW(
            self.model.parameters(),
            lr=self.cfg.learning_rate,
            weight_decay=0.01,
        )
        scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
            optimizer,
            T_max=self.cfg.train_epochs_per_cycle * len(loader),
            eta_min=self.cfg.learning_rate * 0.1,
        )

        losses = []
        for epoch in range(self.cfg.train_epochs_per_cycle):
            epoch_loss = 0.0
            n_batches  = 0
            for x, y in loader:
                x = x.to(DEVICE)
                y = y.to(DEVICE)
                optimizer.zero_grad()
                _, loss = self.model(x, targets=y)
                if loss is None:
                    continue
                loss.backward()
                torch.nn.utils.clip_grad_norm_(
                    self.model.parameters(), self.cfg.gradient_clip
                )
                optimizer.step()
                scheduler.step()
                epoch_loss += loss.item()
                n_batches  += 1
                self._step += 1

            avg = epoch_loss / max(n_batches, 1)
            losses.append(avg)
            self._losses.append(avg)
            logger.info(f"   Epoch {epoch+1}/{self.cfg.train_epochs_per_cycle} "
                        f"loss={avg:.4f}")

        # Perplexidade
        final_loss = losses[-1] if losses else 0.0
        ppl = math.exp(min(final_loss, 20))
        self._perplexities.append(ppl)

        self.model.eval()
        return {
            "final_loss": round(final_loss, 4),
            "perplexity": round(ppl, 2),
            "epochs": self.cfg.train_epochs_per_cycle,
            "steps": self._step,
        }

    def _train_ngram(self, texts: List[str]) -> Dict:
        """Treino incremental do modelo n-grama."""
        self.model.train(texts)
        return {"ngram_contexts": len(self.model._counts)}

    def _save(self):
        try:
            if HAS_TORCH and isinstance(self.model, AtenaTinyTransformer):
                self.model.save(self.cfg.model_dir)
            elif isinstance(self.model, AtenaNgramLM):
                self.model.save(self.cfg.ngram_path)
            if self.tokenizer._trained:
                self.tokenizer.save(self.cfg.vocab_path)
        except Exception as e:
            logger.warning(f"[AtenaLMTrainer] Erro ao salvar: {e}")

    def get_metrics(self) -> Dict:
        return {
            "steps": self._step,
            "recent_loss": round(
                sum(self._losses) / len(self._losses), 4
            ) if self._losses else None,
            "recent_ppl": round(
                sum(self._perplexities) / len(self._perplexities), 2
            ) if self._perplexities else None,
        }


# ═══════════════════════════════════════════════════════════════════════
# 7. GERADOR DE CÓDIGO
# ═══════════════════════════════════════════════════════════════════════

class AtenaLMGenerator:
    """
    Usa o modelo treinado para gerar código Python.
    Substitui/complementa o GrokGenerator nas mutações.
    """

    # Templates de prompt para diferentes tipos de geração
    PROMPTS = {
        "new_function": [
            "def util_sort(",
            "def compute_",
            "def find_",
            "def calculate_",
            "def process_",
            "def validate_",
            "def transform_",
        ],
        "optimization": [
            "def optimized_",
            "@functools.lru_cache\ndef ",
            "def fast_",
        ],
        "algorithm": [
            "def binary_search(",
            "def merge_sort(",
            "def dijkstra(",
            "def dynamic_",
            "def greedy_",
        ],
    }

    def __init__(self, cfg: AtenaLMConfig, tokenizer: AtenaTokenizer, model):
        self.cfg       = cfg
        self.tokenizer = tokenizer
        self.model     = model
        self._gen_count = 0
        self._success_rate_history: deque = deque(maxlen=50)

    def generate_function(self, hint: str = "", category: str = "new_function") -> Optional[str]:
        """Gera uma função Python usando o modelo local."""
        prompts = self.PROMPTS.get(category, self.PROMPTS["new_function"])
        prompt  = hint if hint else random.choice(prompts)

        if HAS_TORCH and isinstance(self.model, AtenaTinyTransformer):
            generated = self._generate_torch(prompt)
        elif isinstance(self.model, AtenaNgramLM):
            generated = self.model.generate_function(prompt)
        else:
            return None

        if not generated:
            return None

        # Pós-processamento: garante que é uma função válida
        cleaned = self._post_process(generated)
        valid = self._validate(cleaned)
        self._gen_count += 1
        self._success_rate_history.append(1.0 if valid else 0.0)
        return cleaned if valid else None

    def _generate_torch(self, prompt: str) -> Optional[str]:
        """Geração com o Transformer."""
        try:
            self.model.eval()
            ids = self.tokenizer.encode(prompt, add_bos=True, add_eos=False)
            ids = ids[:self.cfg.max_seq_len - self.cfg.max_new_tokens]
            idx = torch.tensor([ids], dtype=torch.long, device=DEVICE)
            out = self.model.generate(
                idx,
                max_new_tokens=self.cfg.max_new_tokens,
                temperature=self.cfg.temperature,
                top_k=self.cfg.top_k,
                top_p=self.cfg.top_p,
                repetition_penalty=self.cfg.repetition_penalty,
            )
            full_ids = out[0].tolist()
            return self.tokenizer.decode(full_ids)
        except Exception as e:
            logger.debug(f"[AtenaLMGenerator] Erro na geração: {e}")
            return None

    def _post_process(self, text: str) -> str:
        """Limpa e formata o texto gerado."""
        # Extrai apenas o bloco da função
        lines = text.splitlines()
        func_lines = []
        in_func = False
        indent = None
        for line in lines:
            if line.strip().startswith("def "):
                in_func = True
                indent  = len(line) - len(line.lstrip())
                func_lines = [line]
            elif in_func:
                if line.strip() == "":
                    func_lines.append(line)
                elif len(line) - len(line.lstrip()) > indent or line.strip().startswith("#"):
                    func_lines.append(line)
                else:
                    break  # fim da função
        if func_lines:
            return "\n".join(func_lines).rstrip() + "\n"
        return text.strip() + "\n"

    def _validate(self, code: str) -> bool:
        """Verifica se o código gerado é sintaticamente válido e contém uma função."""
        try:
            tree = ast.parse(code)
            funcs = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
            return len(funcs) > 0
        except Exception:
            return False

    def success_rate(self) -> float:
        if not self._success_rate_history:
            return 0.0
        return sum(self._success_rate_history) / len(self._success_rate_history)

    def stats(self) -> Dict:
        return {
            "generated": self._gen_count,
            "success_rate": round(self.success_rate(), 3),
        }


# ═══════════════════════════════════════════════════════════════════════
# 8. AUTO-AVALIAÇÃO (cria sinal de treino interno)
# ═══════════════════════════════════════════════════════════════════════

class AtenaLMSelfEval:
    """
    A Atena avalia a qualidade de suas próprias gerações,
    criando um sinal de recompensa que alimenta o treino.

    Critérios:
    - Sintaxe válida
    - Complexidade razoável
    - Presença de docstring
    - Comprimento adequado
    - Nenhum padrão proibido
    - Originalidade (não é cópia exata do corpus)
    """

    FORBIDDEN = [
        r'os\.system\s*\(',
        r'__import__\s*\(',
        r'subprocess\.call\s*\(',
    ]

    def __init__(self, corpus_hashes: Optional[set] = None):
        self._forbidden = [re.compile(p) for p in self.FORBIDDEN]
        self._corpus_hashes = corpus_hashes or set()
        self._eval_history: deque = deque(maxlen=200)

    def evaluate(self, code: str) -> Tuple[float, Dict]:
        """
        Retorna (score 0-1, detalhes).
        score=1 → perfeito, score=0 → inútil/proibido.
        """
        details: Dict[str, Any] = {}

        # 1. Sintaxe
        try:
            tree = ast.parse(code)
            details["syntax"] = 1.0
        except SyntaxError as e:
            details["syntax"] = 0.0
            return 0.0, details

        # 2. Funções definidas
        funcs = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
        if not funcs:
            return 0.1, {**details, "has_functions": False}
        details["num_functions"] = len(funcs)
        details["has_functions"] = True

        # 3. Docstrings
        with_docs = sum(1 for f in funcs if ast.get_docstring(f))
        details["doc_ratio"] = with_docs / len(funcs)

        # 4. Comprimento razoável
        lines = code.splitlines()
        n_lines = len(lines)
        if n_lines < 3:
            details["length_score"] = 0.1
        elif n_lines < 50:
            details["length_score"] = 1.0
        else:
            details["length_score"] = max(0.3, 1.0 - (n_lines - 50) / 200)

        # 5. Padrões proibidos
        for pat in self._forbidden:
            if pat.search(code):
                details["forbidden"] = True
                return 0.0, details
        details["forbidden"] = False

        # 6. Originalidade
        code_hash = hashlib.sha256(code.encode()).hexdigest()[:16]
        details["original"] = code_hash not in self._corpus_hashes
        original_bonus = 0.1 if details["original"] else 0.0

        # Score combinado
        score = (
            0.3 * details["syntax"]
          + 0.25 * min(1.0, details["num_functions"] / 3)
          + 0.15 * details["doc_ratio"]
          + 0.20 * details["length_score"]
          + 0.10 * original_bonus
        )
        score = max(0.0, min(1.0, score))
        details["score"] = round(score, 4)
        self._eval_history.append(score)
        return score, details

    def avg_score(self) -> float:
        if not self._eval_history:
            return 0.0
        return round(sum(self._eval_history) / len(self._eval_history), 4)

    def add_corpus_hash(self, code: str):
        self._corpus_hashes.add(
            hashlib.sha256(code.encode()).hexdigest()[:16]
        )


# ═══════════════════════════════════════════════════════════════════════
# 9. MUTAÇÃO VIA MODELO LOCAL
# ═══════════════════════════════════════════════════════════════════════

class AtenaLMMutationPlugin:
    """
    Plugin que adiciona tipos de mutação baseados no modelo local.
    Integra-se ao MutationEngine existente.
    """

    def __init__(self, generator: AtenaLMGenerator, self_eval: AtenaLMSelfEval,
                 dataset: AtenaLMDataset):
        self.generator = generator
        self.self_eval = self_eval
        self.dataset   = dataset
        self._mutation_types = [
            "lm_generate_function",
            "lm_optimize_function",
            "lm_crossover_style",
            "lm_complete_stub",
        ]

    @property
    def mutation_types(self) -> List[str]:
        return self._mutation_types

    def mutate(self, code: str, mutation_type: str) -> Tuple[str, str]:
        """Aplica uma mutação baseada no LM."""
        if mutation_type == "lm_generate_function":
            return self._lm_generate_function(code)
        elif mutation_type == "lm_optimize_function":
            return self._lm_optimize_function(code)
        elif mutation_type == "lm_crossover_style":
            return self._lm_crossover_style(code)
        elif mutation_type == "lm_complete_stub":
            return self._lm_complete_stub(code)
        return code, "Mutação LM desconhecida"

    def _lm_generate_function(self, code: str) -> Tuple[str, str]:
        """Gera uma nova função e a anexa ao código."""
        categories = ["new_function", "algorithm", "optimization"]
        gen = self.generator.generate_function(category=random.choice(categories))
        if not gen:
            return code, "LM: geração falhou"
        score, _ = self.self_eval.evaluate(gen)
        if score < 0.3:
            return code, f"LM: score baixo ({score:.2f})"
        # Adiciona ao dataset para reforço positivo
        self.dataset.add_text(gen, score=score * 100)
        return code + f"\n\n# Gerado pelo modelo local AtenaLM\n{gen}", \
               f"LM: nova função (score={score:.2f})"

    def _lm_optimize_function(self, code: str) -> Tuple[str, str]:
        """Usa o LM para sugerir uma versão otimizada de uma função existente."""
        try:
            tree = ast.parse(code)
            funcs = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
            if not funcs:
                return code, "LM: sem função para otimizar"
            target = max(funcs, key=lambda f: sum(1 for _ in ast.walk(f)))
            import astor
            func_src = astor.to_source(target)
            # Usa como prompt: a função truncada
            hint = func_src[:80]
            gen = self.generator.generate_function(hint=hint, category="optimization")
            if not gen:
                return code, "LM: otimização falhou"
            score, _ = self.self_eval.evaluate(gen)
            if score < 0.4:
                return code, f"LM: otimização score baixo ({score:.2f})"
            return code + f"\n\n# Otimizado pelo AtenaLM\n{gen}", \
                   f"LM: otimização de {target.name} (score={score:.2f})"
        except Exception as e:
            return code, f"LM: erro na otimização ({e})"

    def _lm_crossover_style(self, code: str) -> Tuple[str, str]:
        """
        Gera uma função no 'estilo' de uma aleatória do dataset
        e a combina com o código atual.
        """
        texts = self.dataset.get_texts(max_samples=50, prefer_high_score=True)
        if not texts:
            return code, "LM: dataset vazio para crossover"
        source_text = random.choice(texts)
        # Extrai apenas o começo como prompt
        prompt = source_text[:60] if len(source_text) > 60 else source_text
        gen = self.generator.generate_function(hint=prompt)
        if not gen:
            return code, "LM: crossover de estilo falhou"
        score, _ = self.self_eval.evaluate(gen)
        if score < 0.35:
            return code, f"LM: crossover score baixo ({score:.2f})"
        return code + f"\n\n# Crossover de estilo AtenaLM\n{gen}", \
               f"LM: crossover de estilo (score={score:.2f})"

    def _lm_complete_stub(self, code: str) -> Tuple[str, str]:
        """Detecta funções com apenas 'pass' e tenta completá-las."""
        try:
            tree = ast.parse(code)
            stubs = [
                n for n in ast.walk(tree)
                if isinstance(n, ast.FunctionDef)
                and len(n.body) == 1
                and isinstance(n.body[0], ast.Pass)
            ]
            if not stubs:
                return code, "LM: nenhum stub encontrado"
            import astor
            target = random.choice(stubs)
            hint   = f"def {target.name}("
            gen    = self.generator.generate_function(hint=hint)
            if not gen:
                return code, "LM: stub completion falhou"
            score, _ = self.self_eval.evaluate(gen)
            if score < 0.4:
                return code, f"LM: stub score baixo ({score:.2f})"
            # Substitui o stub no código
            gen_tree = ast.parse(gen)
            gen_funcs = [n for n in ast.walk(gen_tree) if isinstance(n, ast.FunctionDef)]
            if gen_funcs:
                for i, node in enumerate(tree.body):
                    if isinstance(node, ast.FunctionDef) and node.name == target.name:
                        tree.body[i] = gen_funcs[0]
                        tree.body[i].name = target.name
                        break
                ast.fix_missing_locations(tree)
                return astor.to_source(tree), f"LM: stub {target.name} completado"
        except Exception as e:
            return code, f"LM: erro no stub completion ({e})"
        return code, "LM: stub completion sem resultado"


# ═══════════════════════════════════════════════════════════════════════
# 10. COLETA DE DADOS VIA API (sem geração via API)
# ═══════════════════════════════════════════════════════════════════════

class AtenaLMAPIDataCollector:
    """
    Usa APIs externas APENAS para coletar dados de treino.
    Toda a geração é feita pelo modelo local.
    """

    def __init__(self, cfg: AtenaLMConfig, dataset: AtenaLMDataset,
                 grok_generator=None, github_token: str = ""):
        self.cfg       = cfg
        self.dataset   = dataset
        self.grok      = grok_generator
        self.gh_token  = github_token
        self._lock     = threading.RLock()

    def collect_from_grok(self, topics: List[str] = None, n_per_topic: int = 3) -> int:
        """Usa Grok para gerar exemplos de código que alimentam o dataset local."""
        if not self.grok or not self.cfg.use_api_for_data:
            return 0
        if not topics:
            topics = [
                "implements efficient sorting algorithm",
                "parses a JSON structure",
                "validates user input with type checking",
                "implements a simple cache with LRU eviction",
                "finds all palindromes in a list",
                "calculates moving average efficiently",
                "implements binary search tree operations",
                "flattens nested data structures",
            ]
        collected = 0
        for topic in topics[:3]:
            for _ in range(n_per_topic):
                try:
                    code = self.grok.generate_function(topic, max_tokens=300)
                    if code and "def " in code:
                        self.dataset.add_text(code, score=70.0)
                        collected += 1
                        time.sleep(0.5)
                except Exception as e:
                    logger.debug(f"[APICollector] Grok error: {e}")
        logger.info(f"[APICollector] Grok: {collected} exemplos coletados")
        return collected

    def collect_from_github_search(self, queries: List[str] = None) -> int:
        """Busca snippets Python no GitHub como dados de treino."""
        if not self.gh_token or not self.cfg.use_api_for_data:
            return 0
        import requests as req
        session = req.Session()
        session.headers["Authorization"] = f"token {self.gh_token}"
        queries = queries or [
            "language:python algorithm sort",
            "language:python data structure tree",
            "language:python utility helper function",
        ]
        collected = 0
        for query in queries[:2]:
            try:
                resp = session.get(
                    "https://api.github.com/search/code",
                    params={"q": query, "per_page": 5},
                    timeout=10,
                )
                resp.raise_for_status()
                for item in resp.json().get("items", []):
                    try:
                        raw_resp = session.get(
                            item["download_url"] or item["url"],
                            timeout=10,
                        )
                        content = raw_resp.text
                        # Extrai funções
                        try:
                            tree = ast.parse(content)
                            import astor
                            for node in ast.walk(tree):
                                if isinstance(node, ast.FunctionDef):
                                    func_src = astor.to_source(node)
                                    if len(func_src) > 30:
                                        self.dataset.add_text(func_src, score=60.0)
                                        collected += 1
                        except Exception:
                            pass
                    except Exception:
                        pass
                time.sleep(1.0)
            except Exception as e:
                logger.debug(f"[APICollector] GitHub error: {e}")
        logger.info(f"[APICollector] GitHub: {collected} funções coletadas")
        return collected


# ═══════════════════════════════════════════════════════════════════════
# 11. DASHBOARD LM (métricas no dashboard principal)
# ═══════════════════════════════════════════════════════════════════════

class AtenaLMDashboardMixin:
    """
    Adiciona endpoints de métricas LM ao AtenaDashboard existente.
    Integre chamando atena_lm_orchestrator.get_dashboard_state().
    """

    def get_dashboard_state(self) -> Dict:
        """Retorna estado do LM para o dashboard."""
        metrics = self.trainer.get_metrics() if hasattr(self, 'trainer') else {}
        gen_stats = self.generator.stats() if hasattr(self, 'generator') else {}
        dataset_stats = self.dataset.stats() if hasattr(self, 'dataset') else {}
        return {
            "lm_strategy": self.cfg.resolve_strategy(),
            "lm_cycle": self._train_cycle,
            "lm_metrics": metrics,
            "lm_generator": gen_stats,
            "lm_dataset": dataset_stats,
            "lm_selfeval_avg": self.self_eval.avg_score() if hasattr(self, 'self_eval') else 0.0,
            "lm_vocab_size": len(self.tokenizer.token2id) if hasattr(self, 'tokenizer') else 0,
        }


# ═══════════════════════════════════════════════════════════════════════
# 12. ORQUESTRADOR PRINCIPAL
# ═══════════════════════════════════════════════════════════════════════

class AtenaLMOrchestrator(AtenaLMDashboardMixin):
    """
    Ponto de entrada central para o módulo LM.
    
    Integração no AtenaCore:
    
        # Em AtenaCore.__init__:
        from atena_local_lm import AtenaLMOrchestrator
        self.local_lm = AtenaLMOrchestrator(self)
    
        # Em evolve_one_cycle (após registro):
        self.local_lm.on_cycle_end(
            generation=self.generation,
            code=self.current_code,
            metrics=metrics,
            replaced=replaced
        )
    
        # Integrar mutações LM ao MutationEngine:
        self.mutation_engine.mutation_types.extend(
            self.local_lm.plugin.mutation_types
        )
        # Monkey-patch mutate():
        _orig_mutate = self.mutation_engine.mutate
        def _patched_mutate(code, mtype):
            if mtype in self.local_lm.plugin.mutation_types:
                return self.local_lm.plugin.mutate(code, mtype)
            return _orig_mutate(code, mtype)
        self.mutation_engine.mutate = _patched_mutate
    """

    def __init__(self, core):
        self.core    = core
        self.cfg     = AtenaLMConfig()
        self.cfg.setup()

        # Estratégia de modelo
        strategy = self.cfg.resolve_strategy()
        logger.info(f"[AtenaLMOrchestrator] Estratégia: {strategy}")

        # Tokenizer
        self.tokenizer = AtenaTokenizer.load_or_create(
            self.cfg.vocab_path, self.cfg.vocab_size
        )

        # Modelo
        if strategy == "tiny" and HAS_TORCH:
            self.model = AtenaTinyTransformer.load_or_create(
                self.cfg.model_dir, self.cfg
            )
        else:
            self.model = AtenaNgramLM.load_or_create(
                self.cfg.ngram_path, self.cfg.ngram_order
            )

        # Dataset
        self.dataset = AtenaLMDataset(self.cfg, core.kb.conn)

        # Trainer
        self.trainer = AtenaLMTrainer(self.cfg, self.tokenizer, self.model, self.dataset)

        # Generator
        self.generator = AtenaLMGenerator(self.cfg, self.tokenizer, self.model)

        # Self-eval
        self.self_eval = AtenaLMSelfEval()

        # Plugin de mutações
        self.plugin = AtenaLMMutationPlugin(self.generator, self.self_eval, self.dataset)

        # API Collector
        self.api_collector = AtenaLMAPIDataCollector(
            cfg=self.cfg,
            dataset=self.dataset,
            grok_generator=getattr(core.mutation_engine, 'grok', None),
            github_token=getattr(core, 'kb', None) and
                         getattr(core.kb, 'conn', None) and
                         os.getenv("GITHUB_TOKEN", ""),
        )

        self._train_cycle = 0
        self._cycle_count = 0
        self._tokenizer_trained = self.tokenizer._trained
        self._lock = threading.RLock()

        # Bootstrap inicial
        self._bootstrap()

        logger.info("[AtenaLMOrchestrator] ✅ Pronto")
        logger.info(f"   Modelo: {type(self.model).__name__}")
        logger.info(f"   Dataset: {self.dataset.size()} amostras")

    def _bootstrap(self):
        """Coleta dados iniciais e treina o modelo pela primeira vez."""
        logger.info("[AtenaLMOrchestrator] Bootstrap inicial...")

        # Coleta do KB
        added = self.dataset.collect_from_kb(limit=300)
        added += self.dataset.collect_from_evolution(limit=100)

        if self.dataset.size() >= self.cfg.min_train_samples:
            # Treina tokenizer se necessário
            if not self._tokenizer_trained:
                texts = self.dataset.get_texts(max_samples=500)
                logger.info(f"[AtenaLMOrchestrator] Treinando tokenizer em {len(texts)} textos...")
                self.tokenizer.train(texts, num_merges=500)
                self.tokenizer.save(self.cfg.vocab_path)
                self._tokenizer_trained = True

            # Treino inicial
            result = self.trainer.train(cycle=0)
            logger.info(f"[AtenaLMOrchestrator] Bootstrap treino: {result}")
        else:
            logger.info(f"[AtenaLMOrchestrator] Amostras insuficientes para bootstrap "
                        f"({self.dataset.size()}/{self.cfg.min_train_samples})")

        self.dataset.save_corpus()

    def on_cycle_end(self, generation: int, code: str,
                     metrics: Dict, replaced: bool):
        """
        Chamado no final de cada ciclo de evolução.
        - Adiciona o código ao dataset (com score)
        - Treina o modelo a cada N ciclos
        - Atualiza self-eval com hashes do corpus
        """
        self._cycle_count += 1

        # Adiciona código atual ao dataset
        score = metrics.get("score", 0.0)
        if replaced and score > 30:
            self.dataset.add_text(code, score=score)
            self.self_eval.add_corpus_hash(code)

        # Treino incremental
        if self._cycle_count % self.cfg.train_every_n_cycles == 0:
            self._train_cycle += 1
            logger.info(f"\n[AtenaLM] 🧠 Ciclo de treino #{self._train_cycle} "
                        f"(geração {generation})")

            # Coleta dados frescos
            self.dataset.collect_from_kb(limit=200)
            self.dataset.collect_from_evolution(limit=100)

            # Coleta via API (só para dados, não para geração)
            if self.cfg.use_api_for_data and self._train_cycle % 3 == 0:
                threading.Thread(
                    target=self._async_api_collect,
                    daemon=True
                ).start()

            # Treino
            result = self.trainer.train(cycle=self._train_cycle)
            self.dataset.save_corpus()

            # Log de métricas
            lm_metrics = self.trainer.get_metrics()
            logger.info(f"[AtenaLM] Métricas: loss={lm_metrics.get('recent_loss')} "
                        f"ppl={lm_metrics.get('recent_ppl')} "
                        f"gen_success={self.generator.success_rate():.0%}")

        # Persiste métricas no banco
        self._persist_metrics(generation, metrics, replaced)

    def _async_api_collect(self):
        """Coleta assíncrona de dados via API."""
        try:
            self.api_collector.collect_from_grok()
            self.api_collector.collect_from_github_search()
        except Exception as e:
            logger.debug(f"[AtenaLM] API collect error: {e}")

    def _persist_metrics(self, generation: int, metrics: Dict, replaced: bool):
        """Salva métricas do LM no banco SQLite."""
        try:
            lm_m = self.trainer.get_metrics()
            self.core.kb.conn.execute("""
                CREATE TABLE IF NOT EXISTS lm_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    generation INTEGER,
                    timestamp TEXT,
                    train_cycle INTEGER,
                    recent_loss REAL,
                    recent_ppl REAL,
                    dataset_size INTEGER,
                    gen_success_rate REAL,
                    replaced INTEGER
                )
            """)
            self.core.kb.conn.execute("""
                INSERT INTO lm_metrics
                (generation, timestamp, train_cycle, recent_loss, recent_ppl,
                 dataset_size, gen_success_rate, replaced)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                generation,
                datetime.now().isoformat(),
                self._train_cycle,
                lm_m.get("recent_loss"),
                lm_m.get("recent_ppl"),
                self.dataset.size(),
                self.generator.success_rate(),
                1 if replaced else 0,
            ))
            self.core.kb.conn.commit()
        except Exception as e:
            logger.debug(f"[AtenaLM] Erro ao persistir métricas: {e}")

    def integrate_with_mutation_engine(self):
        """
        Integra os tipos de mutação LM ao MutationEngine do core.
        Chame em AtenaCore.__init__ após criar self.local_lm.
        """
        eng = self.core.mutation_engine
        eng.mutation_types.extend(self.plugin.mutation_types)
        _orig = eng.mutate

        def _patched(code: str, mtype: str):
            if mtype in self.plugin.mutation_types:
                return self.plugin.mutate(code, mtype)
            return _orig(code, mtype)

        eng.mutate = _patched
        logger.info(f"[AtenaLM] {len(self.plugin.mutation_types)} tipos de mutação LM integrados")

    def generate(self, hint: str = "", category: str = "new_function") -> Optional[str]:
        """API pública de geração para uso externo."""
        return self.generator.generate_function(hint=hint, category=category)

    def evaluate_code(self, code: str) -> Tuple[float, Dict]:
        """API pública de auto-avaliação."""
        return self.self_eval.evaluate(code)

    def print_status(self):
        """Imprime status completo do módulo LM."""
        logger.info("\n" + "═"*60)
        logger.info("  🧠 ATENA LOCAL LM — STATUS")
        logger.info("═"*60)
        logger.info(f"  Estratégia  : {self.cfg.resolve_strategy()}")
        logger.info(f"  Modelo      : {type(self.model).__name__}")
        logger.info(f"  Ciclos      : {self._cycle_count} evolução | "
                    f"{self._train_cycle} treino")
        lm_m = self.trainer.get_metrics()
        logger.info(f"  Loss recente: {lm_m.get('recent_loss', 'N/A')}")
        logger.info(f"  Perplexidade: {lm_m.get('recent_ppl', 'N/A')}")
        logger.info(f"  Dataset     : {self.dataset.size()} amostras | "
                    f"scored={self.dataset.stats()['scored_samples']}")
        logger.info(f"  Gerador     : {self.generator.stats()}")
        logger.info(f"  Self-eval   : avg={self.self_eval.avg_score():.3f}")
        logger.info("═"*60)


# ═══════════════════════════════════════════════════════════════════════
# PATCH FUNCTION — aplica tudo no AtenaCore com uma linha
# ═══════════════════════════════════════════════════════════════════════

def patch_atena_core(core) -> AtenaLMOrchestrator:
    """
    Aplica o AtenaLocalLM em um AtenaCore já instanciado.

    Uso:
        from atena_local_lm import patch_atena_core
        app = AtenaApp()
        lm = patch_atena_core(app.core)

    Ou dentro do AtenaCore.__init__, no final:
        from atena_local_lm import patch_atena_core
        self.local_lm = patch_atena_core(self)
    """
    lm = AtenaLMOrchestrator(core)
    lm.integrate_with_mutation_engine()

    # Armazena no core
    core.local_lm = lm

    # Salva referência ao on_cycle_end original (se existir)
    _orig_evolve = core.evolve_one_cycle

    def _patched_evolve():
        result = _orig_evolve()
        try:
            # Obtém métricas do último ciclo
            m = core.evaluator.evaluate(core.current_code)
            lm.on_cycle_end(
                generation=core.generation,
                code=core.current_code,
                metrics=m,
                replaced=result.get("replaced", False),
            )
        except Exception as e:
            logger.debug(f"[AtenaLM] Erro no patch on_cycle_end: {e}")
        return result

    core.evolve_one_cycle = _patched_evolve
    logger.info("[patch_atena_core] ✅ AtenaLocalLM integrado ao AtenaCore")
    return lm


# ═══════════════════════════════════════════════════════════════════════
# DEMO STANDALONE
# ═══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s"
    )

    parser = argparse.ArgumentParser(description="AtenaLocalLM — demo standalone")
    parser.add_argument("--demo",    action="store_true", help="Demo de geração")
    parser.add_argument("--train",   action="store_true", help="Treina com código de exemplo")
    parser.add_argument("--status",  action="store_true", help="Status do modelo salvo")
    parser.add_argument("--generate",type=str, default="", help="Gera código com hint")
    args = parser.parse_args()

    cfg = AtenaLMConfig()
    cfg.setup()

    tokenizer = AtenaTokenizer.load_or_create(cfg.vocab_path, cfg.vocab_size)

    if HAS_TORCH:
        model = AtenaTinyTransformer.load_or_create(cfg.model_dir, cfg)
    else:
        model = AtenaNgramLM.load_or_create(cfg.ngram_path, cfg.ngram_order)
        logger.warning("PyTorch não disponível — usando fallback n-grama")

    generator = AtenaLMGenerator(cfg, tokenizer, model)
    self_eval = AtenaLMSelfEval()

    DEMO_CODE = [
        '''def bubble_sort(arr):
    """Ordena lista usando bubble sort."""
    n = len(arr)
    for i in range(n):
        for j in range(0, n - i - 1):
            if arr[j] > arr[j + 1]:
                arr[j], arr[j + 1] = arr[j + 1], arr[j]
    return arr''',
        '''def binary_search(arr, target):
    """Busca binária em lista ordenada."""
    left, right = 0, len(arr) - 1
    while left <= right:
        mid = (left + right) // 2
        if arr[mid] == target:
            return mid
        elif arr[mid] < target:
            left = mid + 1
        else:
            right = mid - 1
    return -1''',
        '''def memoize(func):
    """Decorador de memoização."""
    cache = {}
    def wrapper(*args):
        if args not in cache:
            cache[args] = func(*args)
        return cache[args]
    return wrapper''',
        '''def flatten(lst):
    """Achata lista aninhada."""
    result = []
    for item in lst:
        if isinstance(item, list):
            result.extend(flatten(item))
        else:
            result.append(item)
    return result''',
    ]

    if args.train or args.demo:
        logger.info("Treinando tokenizer...")
        tokenizer.train(DEMO_CODE, num_merges=200)

        # Dataset fictício
        import sqlite3 as _sq
        conn = _sq.connect(":memory:")
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS learned_functions (
                code TEXT, usage_count INTEGER DEFAULT 0, complexity REAL DEFAULT 1.0
            );
            CREATE TABLE IF NOT EXISTS evolution_metrics (generation INTEGER, replaced INTEGER);
            CREATE TABLE IF NOT EXISTS episodic_memory (generation INTEGER, code_snapshot TEXT);
        """)
        for c in DEMO_CODE:
            conn.execute("INSERT INTO learned_functions VALUES (?, 1, 1.0)", (c,))
        conn.commit()

        dataset = AtenaLMDataset(cfg, conn)
        for c in DEMO_CODE:
            dataset.add_text(c, score=80.0)

        trainer = AtenaLMTrainer(cfg, tokenizer, model, dataset)
        logger.info("Treinando modelo...")
        result = trainer.train(cycle=1)
        logger.info(f"Resultado: {result}")

    if args.demo or args.generate:
        hint = args.generate or ""
        logger.info(f"\n🎯 Gerando função (hint='{hint}')...")
        for i in range(3):
            gen = generator.generate_function(hint=hint)
            if gen:
                score, details = self_eval.evaluate(gen)
                logger.info(f"\n--- Geração {i+1} (score={score:.2f}) ---")
                print(gen)
                logger.info(f"Detalhes: {details}")
            else:
                logger.info(f"Geração {i+1}: falhou")

    if args.status:
        logger.info(f"\n📊 Status do modelo:")
        logger.info(f"  Tipo: {type(model).__name__}")
        logger.info(f"  Vocab: {len(tokenizer.token2id)} tokens")
        logger.info(f"  Gerador stats: {generator.stats()}")
        if hasattr(model, 'cfg'):
            n = sum(p.numel() for p in model.parameters())
            logger.info(f"  Parâmetros: {n/1e6:.2f}M")

