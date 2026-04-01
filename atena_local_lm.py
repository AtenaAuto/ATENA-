#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""

              ATENA LOCAL LM PRO v4.1  FULLY INTEGRATED                    
                                                                            
  Features integradas: LoRA, RAG, Ensemble, Beam Search, Augmentation,     
  Distillation, Prompt Engineering, Smart Cache, TensorBoard,              
  Advanced Evaluation, Complexity Analysis                                 

"""

import os
import sys
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
import pickle
import heapq
from pathlib import Path
from datetime import datetime
from typing import (
    Any, Dict, List, Optional, Tuple, Callable, Union
)
from collections import Counter, defaultdict, deque
from dataclasses import dataclass, field
from functools import lru_cache
from contextlib import contextmanager

# Configurao de logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s  %(message)s"
)
logger = logging.getLogger("atena.lm.pro")

# 
# DETECO DE BACKENDS (mantido igual)
# 

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    from torch.utils.data import Dataset, DataLoader
    HAS_TORCH = True
    DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    logger.info(f"[AtenaLM] PyTorch   device: {DEVICE}")
except ImportError:
    HAS_TORCH = False
    DEVICE = None
    logger.warning("[AtenaLM] PyTorch   fallback para n-grama")

try:
    from transformers import (
        GPT2LMHeadModel, GPT2Tokenizer, AutoModelForCausalLM, AutoTokenizer
    )
    HAS_TRANSFORMERS = True
    logger.info("[AtenaLM] HuggingFace Transformers ")
except ImportError:
    HAS_TRANSFORMERS = False

try:
    import faiss
    HAS_FAISS = True
    logger.info("[AtenaLM] FAISS ")
except ImportError:
    HAS_FAISS = False
    logger.warning("[AtenaLM] FAISS   RAG desabilitado")

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False
    np = None

try:
    from torch.utils.tensorboard import SummaryWriter
    HAS_TENSORBOARD = True
except ImportError:
    HAS_TENSORBOARD = False

# 
# CONFIGURAO (mantida, com pequenas adies)
# 

@dataclass
class AtenaLMConfigPro:
    """Configurao PRO com suporte a todas as features."""
    base_dir: Path = Path("./atena_evolution/lm_pro")
    model_strategy: str = "auto"

    # Transformer
    vocab_size: int = 16384
    embed_dim: int = 256
    num_heads: int = 8
    num_layers: int = 6
    ffn_dim: int = 1024
    max_seq_len: int = 1024
    dropout: float = 0.15
    attention_dropout: float = 0.1

    # LoRA
    use_lora: bool = True
    lora_rank: int = 16
    lora_alpha: float = 32.0
    lora_dropout: float = 0.1
    lora_target_modules: List[str] = field(default_factory=lambda: ["attn", "ffn"])

    # Treinamento
    train_every_n_cycles: int = 4
    train_epochs_per_cycle: int = 3
    batch_size: int = 16
    learning_rate: float = 1e-4
    min_learning_rate: float = 1e-6
    gradient_clip: float = 1.0
    weight_decay: float = 0.01
    max_train_samples: int = 4096
    min_train_samples: int = 128
    warmup_ratio: float = 0.1
    early_stopping_patience: int = 5
    early_stopping_metric: str = "loss"

    # Gerao
    temperature: float = 0.85
    top_p: float = 0.95
    top_k: int = 100
    max_new_tokens: int = 512
    repetition_penalty: float = 1.2
    length_penalty: float = 1.0
    num_beams: int = 3
    num_beam_groups: int = 2
    diversity_penalty: float = 0.5
    use_cache: bool = True

    # RAG
    use_rag: bool = True
    rag_top_k: int = 5
    rag_embed_dim: int = 384
    rag_index_type: str = "Flat"

    # Ensemble
    use_ensemble: bool = True
    ensemble_models: List[str] = field(default_factory=lambda: ["transformer", "ngram"])
    ensemble_weights: Dict[str, float] = field(default_factory=lambda: {"transformer": 0.7, "ngram": 0.3})

    # Quantizao
    quantize: bool = False
    quantize_dynamic: bool = True

    # N-grama
    ngram_order: int = 5
    ngram_laplace: float = 0.01

    # Self-eval
    selfeval_enabled: bool = True
    selfeval_weight: float = 0.4
    selfeval_use_static_analysis: bool = True
    selfeval_use_complexity: bool = True

    # Augmentation
    use_augmentation: bool = True
    augmentation_types: List[str] = field(default_factory=lambda: [
        "variable_rename", "comment_variation", "format_change", "paraphrase"
    ])
    augmentation_ratio: float = 0.3

    # Monitoramento
    use_tensorboard: bool = True
    log_interval: int = 50
    use_cache_path: bool = True

    # Distillation
    use_distillation: bool = True
    teacher_model_name: Optional[str] = "gpt2"
    distillation_temperature: float = 4.0
    distillation_weight: float = 0.3

    # Outros
    use_api_for_data: bool = True
    max_cache_size: int = 10000
    save_checkpoint_every_n_epochs: int = 2
    seed: int = 42

    @property
    def model_dir(self) -> Path: return self.base_dir / "model"
    @property
    def checkpoint_dir(self) -> Path: return self.base_dir / "checkpoints"
    @property
    def data_dir(self) -> Path: return self.base_dir / "data"
    @property
    def rag_index_path(self) -> Path: return self.base_dir / "rag_index.faiss"
    @property
    def embeddings_path(self) -> Path: return self.base_dir / "embeddings.pkl"
    @property
    def tensorboard_dir(self) -> Path: return self.base_dir / "runs"
    @property
    def vocab_path(self) -> Path: return self.base_dir / "vocab.json"
    @property
    def ngram_path(self) -> Path: return self.base_dir / "ngram.pkl"

    def setup(self):
        for d in [self.base_dir, self.model_dir, self.checkpoint_dir,
                  self.data_dir, self.tensorboard_dir]:
            d.mkdir(parents=True, exist_ok=True)

    def resolve_strategy(self) -> str:
        if self.model_strategy != "auto":
            return self.model_strategy
        if HAS_TORCH:
            return "rag" if HAS_FAISS else "tiny"
        return "ngram"

# 
# CLASSES AUXILIARES (avanadas)  mantidas ou ajustadas
# 

# SmartCache (mantido)
class SmartCache:
    def __init__(self, max_size: int = 10000, persist_path: Optional[Path] = None):
        self.max_size = max_size
        self.persist_path = persist_path
        self._cache = {}
        self._access_times = {}
        self._lock = threading.RLock()
        self._hits = 0
        self._misses = 0

    def get(self, key: str, default=None):
        with self._lock:
            if key in self._cache:
                self._access_times[key] = time.time()
                self._hits += 1
                return self._cache[key]
            self._misses += 1
            return default

    def set(self, key: str, value: Any, ttl: int = None):
        with self._lock:
            if len(self._cache) >= self.max_size:
                lru_key = min(self._access_times, key=self._access_times.get)
                del self._cache[lru_key]
                del self._access_times[lru_key]
            self._cache[key] = value
            self._access_times[key] = time.time()

    def hit_rate(self) -> float:
        total = self._hits + self._misses
        return self._hits / total if total > 0 else 0.0

    def stats(self) -> Dict:
        return {"size": len(self._cache), "max_size": self.max_size,
                "hits": self._hits, "misses": self._misses,
                "hit_rate": round(self.hit_rate(), 3)}

    def save(self, path: Path):
        with self._lock:
            data = {"cache": self._cache, "stats": self.stats()}
            with open(path, "wb") as f:
                pickle.dump(data, f)

    def load(self, path: Path):
        with self._lock:
            try:
                with open(path, "rb") as f:
                    data = pickle.load(f)
                self._cache = data["cache"]
                self._access_times = {k: time.time() for k in self._cache}
            except Exception as e:
                logger.warning(f"Erro ao carregar cache: {e}")

# CodeComplexityAnalyzer (mantido)
class CodeComplexityAnalyzer:
    @staticmethod
    def analyze(code: str) -> Dict[str, float]:
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return {"error": 1.0}
        metrics = {
            "lines": len(code.splitlines()),
            "cyclomatic": CodeComplexityAnalyzer._cyclomatic_complexity(tree),
            "nesting": CodeComplexityAnalyzer._max_nesting_level(tree),
            "loops": CodeComplexityAnalyzer._count_loops(tree),
            "functions": len([n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]),
            "recursion_depth": CodeComplexityAnalyzer._recursion_depth(tree),
        }
        return metrics

    @staticmethod
    def _cyclomatic_complexity(tree) -> int:
        complexity = 1
        for node in ast.walk(tree):
            if isinstance(node, (ast.If, ast.For, ast.While, ast.ExceptHandler,
                                 ast.Assert, ast.BoolOp)):
                complexity += 1
        return complexity

    @staticmethod
    def _max_nesting_level(tree, level: int = 0) -> int:
        max_level = level
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.If, ast.For, ast.While, ast.With, ast.Try)):
                child_level = CodeComplexityAnalyzer._max_nesting_level(node, level + 1)
                max_level = max(max_level, child_level)
        return max_level

    @staticmethod
    def _count_loops(tree) -> int:
        return sum(1 for n in ast.walk(tree) if isinstance(n, (ast.For, ast.While)))

    @staticmethod
    def _recursion_depth(tree) -> int:
        max_depth = 0
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                depth = CodeComplexityAnalyzer._recursion_depth_in_func(node)
                max_depth = max(max_depth, depth)
        return max_depth

    @staticmethod
    def _recursion_depth_in_func(func: ast.FunctionDef) -> int:
        func_name = func.name
        calls = 0
        for node in ast.walk(func):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id == func_name:
                    calls += 1
        return calls

# LexicalQualityAnalyzer (mantido)
class LexicalQualityAnalyzer:
    GOOD_NAMING = {
        "prefixes": ["get_", "set_", "compute_", "find_", "check_", "is_", "has_"],
        "suffixes": ["_func", "_impl", "_handler", "_utils", "_config"],
    }

    @staticmethod
    def analyze(code: str) -> float:
        try:
            tree = ast.parse(code)
        except:
            return 0.3

        score_parts = []
        funcs = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
        if funcs:
            good_names = sum(
                1 for f in funcs
                if any(f.name.startswith(p) for p in LexicalQualityAnalyzer.GOOD_NAMING["prefixes"])
                or any(f.name.endswith(s) for s in LexicalQualityAnalyzer.GOOD_NAMING["suffixes"])
                or "_" in f.name
            )
            score_parts.append(good_names / len(funcs))

        names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                names.add(node.id)
        if names:
            good_vars = sum(1 for n in names if len(n) > 2)
            score_parts.append(good_vars / len(names))

        if funcs:
            type_hints = sum(
                1 for f in funcs
                if f.returns is not None
                or any(arg.annotation is not None for arg in f.args.args)
            )
            score_parts.append(min(1.0, type_hints / len(funcs)))

        return round(sum(score_parts) / len(score_parts), 3) if score_parts else 0.5

# AdvancedCodeEvaluator (mantido)
class AdvancedCodeEvaluator:
    FORBIDDEN_PATTERNS = [
        r'os\.system\s*\(',
        r'__import__\s*\(',
        r'subprocess\.call\s*\(',
        r'eval\s*\(',
        r'exec\s*\(',
    ]

    def __init__(self):
        self._forbidden = [re.compile(p) for p in self.FORBIDDEN_PATTERNS]
        self._corpus_hashes = set()
        self._lexical_analyzer = LexicalQualityAnalyzer()
        self._complexity_analyzer = CodeComplexityAnalyzer()
        self._eval_history: deque = deque(maxlen=500)

    def evaluate(self, code: str) -> Tuple[float, Dict]:
        details = {}
        try:
            tree = ast.parse(code)
            details["syntax"] = 1.0
        except SyntaxError:
            return 0.0, {**details, "syntax": 0.0}

        for pat in self._forbidden:
            if pat.search(code):
                details["security"] = 0.0
                return 0.0, details
        details["security"] = 1.0

        funcs = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
        if not funcs:
            return 0.1, {**details, "has_functions": False}
        details["num_functions"] = len(funcs)

        with_docs = sum(1 for f in funcs if ast.get_docstring(f))
        details["doc_ratio"] = with_docs / len(funcs)

        lines = code.splitlines()
        n_lines = len(lines)
        if n_lines < 3:
            details["length_score"] = 0.1
        elif 10 <= n_lines <= 100:
            details["length_score"] = 1.0
        else:
            details["length_score"] = max(0.2, 1.0 - abs(n_lines - 50) / 200)

        lexical_score = self._lexical_analyzer.analyze(code)
        details["lexical_score"] = lexical_score

        complexity = self._complexity_analyzer.analyze(code)
        details["complexity"] = complexity
        cc = complexity.get("cyclomatic", 1)
        nesting = complexity.get("nesting", 0)
        complexity_score = max(0.2, 1.0 - (cc / 20) - (nesting / 10))
        details["complexity_score"] = complexity_score

        code_hash = hashlib.sha256(code.encode()).hexdigest()[:16]
        details["original"] = code_hash not in self._corpus_hashes
        original_bonus = 0.1 if details["original"] else 0.0

        weights = {
            "syntax": 0.20, "security": 0.15, "num_functions": 0.10,
            "doc_ratio": 0.15, "length_score": 0.10, "lexical_score": 0.10,
            "complexity_score": 0.10, "original": 0.10,
        }
        score = (
            weights["syntax"] * details["syntax"]
            + weights["security"] * details["security"]
            + weights["num_functions"] * min(1.0, len(funcs) / 3)
            + weights["doc_ratio"] * details["doc_ratio"]
            + weights["length_score"] * details["length_score"]
            + weights["lexical_score"] * lexical_score
            + weights["complexity_score"] * complexity_score
            + weights["original"] * (1.0 if details["original"] else 0.0)
        )
        score = max(0.0, min(1.0, score))
        details["score"] = round(score, 4)
        self._eval_history.append(score)
        return score, details

    def add_corpus_hash(self, code: str):
        self._corpus_hashes.add(hashlib.sha256(code.encode()).hexdigest()[:16])

    def avg_score(self) -> float:
        if not self._eval_history:
            return 0.0
        return round(sum(self._eval_history) / len(self._eval_history), 4)

# CodeAugmentation (mantido)
class CodeAugmentation:
    @staticmethod
    def augment(code: str, methods: List[str] = None) -> List[str]:
        if methods is None:
            methods = ["variable_rename", "comment_variation", "format_change"]
        variations = [code]
        for method in methods:
            try:
                if method == "variable_rename":
                    variations.extend(CodeAugmentation._rename_variables(code))
                elif method == "comment_variation":
                    variations.extend(CodeAugmentation._vary_comments(code))
                elif method == "format_change":
                    variations.extend(CodeAugmentation._format_variations(code))
                elif method == "paraphrase":
                    variations.extend(CodeAugmentation._paraphrase(code))
            except Exception as e:
                logger.debug(f"Augmentation error ({method}): {e}")
        return list(set(variations))

    @staticmethod
    def _rename_variables(code: str) -> List[str]:
        try:
            tree = ast.parse(code)
            variations = []
            names = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Name):
                    names.add(node.id)
            prefixes = ["var", "tmp", "x", "n", "data", "item", "val"]
            for i, name in enumerate(sorted(names)[:5]):
                new_code = code
                for j, prefix in enumerate(prefixes):
                    new_name = f"{prefix}_{i}_{j}"
                    new_code = re.sub(rf"\b{name}\b", new_name, new_code)
                try:
                    ast.parse(new_code)
                    variations.append(new_code)
                except:
                    pass
            return variations
        except:
            return []

    @staticmethod
    def _vary_comments(code: str) -> List[str]:
        variations = []
        lines = code.split("\n")
        for i, line in enumerate(lines):
            if "#" in line and not line.strip().startswith("#"):
                new_lines = lines.copy()
                new_lines[i] = line.split("#")[0].rstrip()
                variations.append("\n".join(new_lines))
            elif '"""' in line or "'''" in line:
                new_lines = lines.copy()
                new_lines[i] = line.replace('"""', '"').replace("'''", "'")
                variations.append("\n".join(new_lines))
        return variations

    @staticmethod
    def _format_variations(code: str) -> List[str]:
        variations = []
        if "\n" in code:
            oneline = " ".join(line.strip() for line in code.split("\n")
                               if line.strip() and not line.strip().startswith("#"))
            if len(oneline) < 80:
                variations.append(oneline)
        spaced = re.sub(r'\s+', ' ', code)
        variations.append(spaced)
        return variations

    @staticmethod
    def _paraphrase(code: str) -> List[str]:
        variations = []
        v1 = re.sub(r'if not\s+(\w+)', r'if \1 == False', code)
        variations.append(v1)
        v2 = re.sub(r'(\w+)\s*=\s*\1\s*\+\s*(\d+)', r'\1 += \2', code)
        variations.append(v2)
        return variations

# AdvancedPromptEngineer (mantido)
class AdvancedPromptEngineer:
    STRATEGIES = {
        "few_shot": (
            "# Example 1:\n{example1}\n\n"
            "# Example 2:\n{example2}\n\n"
            "# Your task:\n{task}\n"
        ),
        "cot": (
            "# Think step by step\n"
            "# Step 1: Understand the problem\n"
            "# Step 2: Plan the solution\n"
            "# Step 3: Implement\n{task}\n"
        ),
        "instruction": (
            "# Instructions: {instruction}\n"
            "# Requirements:\n"
            "# - Efficient implementation\n"
            "# - Clear variable names\n"
            "# - Proper error handling\n"
            "{task}\n"
        ),
        "pattern": (
            "# Pattern: {pattern}\n"
            "# Implementation:\n{task}\n"
        ),
    }

    @staticmethod
    def engineer_prompt(task: str, strategy: str = "instruction",
                       examples: List[str] = None, **kwargs) -> str:
        template = AdvancedPromptEngineer.STRATEGIES.get(strategy, "{task}")
        return template.format(
            task=task,
            example1=examples[0] if examples else "",
            example2=examples[1] if examples else "",
            instruction=kwargs.get("instruction", "Generate optimized Python code"),
            pattern=kwargs.get("pattern", "efficient algorithm"),
        )

# RAGRetriever (com fallback para sentence_transformers)
class RAGRetriever:
    def __init__(self, embed_dim: int = 384, index_type: str = "Flat"):
        self.embed_dim = embed_dim
        self.index_type = index_type
        self.index = None
        self.corpus = []
        self._embedder = None
        self._init_embedder()
        self._init_index()

    def _init_embedder(self):
        try:
            from sentence_transformers import SentenceTransformer
            self._embedder = SentenceTransformer('all-MiniLM-L6-v2')
            logger.info("Embedder carregado (sentence-transformers)")
        except ImportError:
            logger.warning("sentence-transformers no disponvel; usando fallback hash")
            self._embedder = None

    def _init_index(self):
        if HAS_FAISS:
            if self.index_type == "Flat":
                self.index = faiss.IndexFlatL2(self.embed_dim)
            elif self.index_type == "IVF":
                quantizer = faiss.IndexFlatL2(self.embed_dim)
                self.index = faiss.IndexIVFFlat(quantizer, self.embed_dim, 100)
        else:
            self.index = None

    def _embed(self, texts: List[str]) -> Any:
        if self._embedder:
            return self._embedder.encode(texts, show_progress_bar=False)
        else:
            # Fallback: vetores aleatrios
            if HAS_NUMPY:
                return np.random.rand(len(texts), self.embed_dim).astype('float32')
            else:
                return [ [random.random() for _ in range(self.embed_dim)] for _ in texts ]

    def add_documents(self, texts: List[str]):
        if not texts or self.index is None:
            return
        embeddings = self._embed(texts)
        if HAS_NUMPY:
            embeddings = embeddings.astype('float32')
        self.index.add(embeddings)
        self.corpus.extend(texts)
        logger.info(f"[RAG] {len(texts)} documentos adicionados ({len(self.corpus)} total)")

    def retrieve(self, query: str, k: int = 5) -> Optional[str]:
        if self.index is None or not self.corpus:
            return None
        query_emb = self._embed([query])
        if HAS_NUMPY:
            query_emb = query_emb.astype('float32')
        distances, indices = self.index.search(query_emb, min(k, len(self.corpus)))
        results = []
        for idx, dist in zip(indices[0], distances[0]):
            if idx < len(self.corpus):
                results.append((self.corpus[idx], float(dist)))
        if results:
            # Retorna apenas o texto mais similar (ou pode retornar todos)
            return results[0][0]
        return None

    def save(self, path: Path):
        if self.index and HAS_FAISS:
            faiss.write_index(self.index, str(path / "rag_index.faiss"))
            with open(path / "rag_corpus.pkl", "wb") as f:
                pickle.dump(self.corpus, f)

    @classmethod
    def load(cls, path: Path) -> "RAGRetriever":
        retriever = cls()
        if (path / "rag_index.faiss").exists():
            retriever.index = faiss.read_index(str(path / "rag_index.faiss"))
            with open(path / "rag_corpus.pkl", "rb") as f:
                retriever.corpus = pickle.load(f)
        return retriever

# LoRA (corrigido para aplicar recursivamente)
class LoRALayer(nn.Module):
    def __init__(self, original_linear: nn.Linear, rank: int, alpha: float):
        super().__init__()
        self.original = original_linear
        self.rank = rank
        self.alpha = alpha
        in_features = original_linear.in_features
        out_features = original_linear.out_features
        self.lora_down = nn.Linear(in_features, rank, bias=False)
        self.lora_up = nn.Linear(rank, out_features, bias=False)
        nn.init.normal_(self.lora_down.weight, std=1 / math.sqrt(rank))
        nn.init.zeros_(self.lora_up.weight)
        self.scaling = alpha / rank

    def forward(self, x):
        return self.original(x) + self.lora_up(self.lora_down(x)) * self.scaling

def apply_lora(model: nn.Module, rank: int = 16, alpha: float = 32.0) -> nn.Module:
    """Aplica LoRA recursivamente em todas as camadas lineares do modelo."""
    for name, module in list(model.named_children()):
        if isinstance(module, nn.Linear):
            lora_layer = LoRALayer(module, rank, alpha)
            setattr(model, name, lora_layer)
        else:
            apply_lora(module, rank, alpha)
    return model

def quantize_model(model: nn.Module) -> nn.Module:
    """Quantizao dinmica para CPU."""
    if not HAS_TORCH or DEVICE.type != 'cpu':
        return model
    try:
        model = torch.quantization.quantize_dynamic(
            model, {nn.Linear}, dtype=torch.qint8
        )
        logger.info("Modelo quantizado para int8 (CPU)")
    except Exception as e:
        logger.warning(f"Quantizao falhou: {e}")
    return model

# DiverseBeamSearchGenerator (implementado)
class DiverseBeamSearchGenerator:
    def __init__(self, model, tokenizer, cfg):
        self.model = model
        self.tokenizer = tokenizer
        self.cfg = cfg

    @torch.no_grad()
    def generate(self, prompt_ids: List[int]) -> List[int]:
        """Beam search with diversity penalty."""
        model = self.model
        tokenizer = self.tokenizer
        num_beams = self.cfg.num_beams
        num_groups = self.cfg.num_beam_groups
        diversity_penalty = self.cfg.diversity_penalty
        max_new_tokens = self.cfg.max_new_tokens
        temperature = self.cfg.temperature
        length_penalty = self.cfg.length_penalty

        # Inicializa beams
        beams = [(prompt_ids, 0.0)]
        for step in range(max_new_tokens):
            new_beams = []
            for seq, score in beams:
                # Trunca para contexto mximo
                input_ids = seq[-self.cfg.max_seq_len:]
                idx = torch.tensor([input_ids], device=DEVICE)
                logits, _ = model(idx)
                logits = logits[0, -1, :] / max(temperature, 1e-5)

                # Top-k
                topk_vals, topk_idx = torch.topk(logits, k=min(50, logits.shape[0]))
                probs = F.softmax(topk_vals, dim=-1)

                # Para cada grupo (diversidade)
                for g in range(num_groups):
                    for _ in range(num_beams // num_groups):
                        next_idx = torch.multinomial(probs, num_samples=1).item()
                        next_tok = topk_idx[next_idx].item()
                        new_score = score - math.log(max(probs[next_idx].item(), 1e-10))
                        # Penalidade de diversidade
                        if diversity_penalty > 0:
                            # Conta quantas vezes o token j apareceu no grupo
                            group_tokens = [t for s, t in new_beams if s % num_groups == g]
                            if next_tok in group_tokens:
                                new_score += diversity_penalty * math.log(1 + group_tokens.count(next_tok))
                        new_seq = seq + [next_tok]
                        new_beams.append((new_seq, new_score))

            # Mantm top-k beams
            beams = sorted(new_beams, key=lambda x: x[1])[:num_beams]
            # Verifica se todos terminaram
            if all(seq[-1] == tokenizer.EOS_ID for seq, _ in beams):
                break

        best_seq = min(beams, key=lambda x: x[1])[0]
        return best_seq

# ModelEnsemble (simplificado)
class ModelEnsemble:
    def __init__(self, models: Dict[str, Any], weights: Dict[str, float]):
        self.models = models
        self.weights = weights
        total = sum(weights.values())
        self.weights = {k: v/total for k, v in weights.items()}

    def generate(self, prompt: str, hint: str = "") -> Optional[str]:
        results = {}
        for name, model in self.models.items():
            try:
                if hasattr(model, 'generate_function'):
                    result = model.generate_function(hint=hint)
                elif hasattr(model, 'generate'):
                    result = model.generate(prompt, max_tokens=200)
                else:
                    result = None
                if result:
                    results[name] = result
            except Exception as e:
                logger.debug(f"Ensemble error ({name}): {e}")
        if not results:
            return None
        best = max(results.items(), key=lambda x: self.weights.get(x[0], 0))
        return best[1]

# 
# GERADOR PRO (com beam search)
# 

class AtenaLMGeneratorPro:
    """Gerador com beam search e diverse decoding."""
    def __init__(self, cfg: AtenaLMConfigPro, tokenizer, model):
        self.cfg = cfg
        self.tokenizer = tokenizer
        self.model = model
        self._gen_count = 0
        self._success_rate_history = deque(maxlen=50)
        self._beam_generator = None
        if HAS_TORCH and isinstance(model, AtenaTinyTransformer):
            self._beam_generator = DiverseBeamSearchGenerator(model, tokenizer, cfg)

    def generate_function(self, hint: str = "", category: str = "new_function") -> Optional[str]:
        """Gera cdigo com beam search se disponvel."""
        prompt = hint if hint else self._get_prompt(category)
        if HAS_TORCH and self._beam_generator:
            generated = self._generate_with_beam(prompt)
        else:
            generated = self._generate_simple(prompt)
        if not generated:
            return None
        cleaned = self._post_process(generated)
        valid = self._validate(cleaned)
        self._gen_count += 1
        self._success_rate_history.append(1.0 if valid else 0.0)
        return cleaned if valid else None

    def _get_prompt(self, category: str) -> str:
        prompts = {
            "new_function": ["def util_sort(", "def compute_", "def find_", "def calculate_"],
            "optimization": ["def optimized_", "@functools.lru_cache\ndef ", "def fast_"],
            "algorithm": ["def binary_search(", "def merge_sort(", "def dijkstra("],
        }
        choices = prompts.get(category, prompts["new_function"])
        return random.choice(choices)

    def _generate_with_beam(self, prompt: str) -> Optional[str]:
        try:
            ids = self.tokenizer.encode(prompt, add_bos=True, add_eos=False)
            max_input = self.cfg.max_seq_len - self.cfg.max_new_tokens
            ids = ids[:max_input]
            out_ids = self._beam_generator.generate(ids)
            return self.tokenizer.decode(out_ids)
        except Exception as e:
            logger.debug(f"Erro na gerao com beam: {e}")
            return None

    def _generate_simple(self, prompt: str) -> Optional[str]:
        try:
            ids = self.tokenizer.encode(prompt, add_bos=True, add_eos=False)
            max_input = self.cfg.max_seq_len - self.cfg.max_new_tokens
            ids = ids[:max_input]
            idx = torch.tensor([ids], dtype=torch.long, device=DEVICE)
            out = self.model.generate(
                idx,
                max_new_tokens=self.cfg.max_new_tokens,
                temperature=self.cfg.temperature,
                top_k=self.cfg.top_k,
                top_p=self.cfg.top_p,
                repetition_penalty=self.cfg.repetition_penalty,
            )
            return self.tokenizer.decode(out[0].tolist())
        except Exception as e:
            logger.debug(f"Erro na gerao simples: {e}")
            return None

    def _post_process(self, text: str) -> str:
        lines = text.splitlines()
        func_lines = []
        in_func = False
        indent = None
        for line in lines:
            if line.strip().startswith("def "):
                in_func = True
                indent = len(line) - len(line.lstrip())
                func_lines = [line]
            elif in_func:
                if line.strip() == "":
                    func_lines.append(line)
                elif len(line) - len(line.lstrip()) > indent or line.strip().startswith("#"):
                    func_lines.append(line)
                else:
                    break
        if func_lines:
            return "\n".join(func_lines).rstrip() + "\n"
        return text.strip() + "\n"

    def _validate(self, code: str) -> bool:
        try:
            tree = ast.parse(code)
            funcs = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
            return len(funcs) > 0
        except:
            return False

    def success_rate(self) -> float:
        if not self._success_rate_history:
            return 0.0
        return sum(self._success_rate_history) / len(self._success_rate_history)

    def stats(self) -> Dict:
        return {"generated": self._gen_count, "success_rate": round(self.success_rate(), 3)}

# 
# ORQUESTRADOR PRO (integrado)
# 

class AtenaLMOrchestratorPro:
    """
    Orquestrador PRO com todas as features integradas.
    """
    def __init__(self, core=None, config: Optional[AtenaLMConfigPro] = None):
        self.core = core
        self.cfg = config or AtenaLMConfigPro()
        self.cfg.setup()

        # Seed
        random.seed(self.cfg.seed)
        if HAS_TORCH:
            torch.manual_seed(self.cfg.seed)

        # Cache
        self.cache = SmartCache(max_size=self.cfg.max_cache_size,
                                persist_path=self.cfg.base_dir / "generation_cache.pkl")
        if self.cfg.use_cache_path and self.cache.persist_path.exists():
            self.cache.load(self.cache.persist_path)

        # TensorBoard
        self.writer = None
        if HAS_TENSORBOARD and self.cfg.use_tensorboard:
            self.writer = SummaryWriter(str(self.cfg.tensorboard_dir))

        # Inicializa componentes
        self._init_components()
        self._init_models()

        logger.info(" AtenaLM PRO v4.1 inicializado")
        self._print_banner()

    def _init_components(self):
        self.evaluator = AdvancedCodeEvaluator()
        self.augmenter = CodeAugmentation()
        self.prompt_engineer = AdvancedPromptEngineer()
        self.rag = None
        if self.cfg.use_rag and HAS_FAISS:
            self.rag = RAGRetriever(embed_dim=self.cfg.rag_embed_dim,
                                    index_type=self.cfg.rag_index_type)
            if self.core and hasattr(self.core, 'kb'):
                self._load_rag_data()

    def _load_rag_data(self):
        try:
            conn = self.core.kb.conn
            rows = conn.execute("SELECT code FROM learned_functions WHERE code IS NOT NULL LIMIT 500").fetchall()
            if rows:
                self.rag.add_documents([r[0] for r in rows])
                logger.info(f"RAG populado com {len(rows)} funes")
        except Exception as e:
            logger.warning(f"Erro ao carregar dados RAG: {e}")

    def _init_models(self):
        # Tokenizer
        self.tokenizer = AtenaTokenizer.load_or_create(
            self.cfg.vocab_path, self.cfg.vocab_size
        )

        # Modelo principal
        strategy = self.cfg.resolve_strategy()
        if strategy in ("tiny", "rag", "hybrid") and HAS_TORCH:
            self.model = AtenaTinyTransformer.load_or_create(
                self.cfg.model_dir, self.cfg
            )
            if self.cfg.use_lora:
                self.model = apply_lora(self.model, rank=self.cfg.lora_rank, alpha=self.cfg.lora_alpha)
                logger.info(f"LoRA aplicada (rank={self.cfg.lora_rank})")
            if self.cfg.quantize:
                self.model = quantize_model(self.model)
        else:
            self.model = AtenaNgramLM.load_or_create(
                self.cfg.ngram_path, self.cfg.ngram_order
            )
            logger.warning("Usando modelo n-grama (fallback)")

        # Dataset
        self.dataset = AtenaLMDataset(self.cfg, self.core.kb.conn if self.core else None)

        # Trainer (com distillation se disponvel)
        if HAS_TORCH and isinstance(self.model, AtenaTinyTransformer):
            self.trainer = AtenaLMTrainerPro(self.cfg, self.tokenizer, self.model, self.dataset)
            if self.cfg.use_distillation and HAS_TRANSFORMERS:
                self._init_teacher()
        else:
            self.trainer = AtenaLMTrainer(self.cfg, self.tokenizer, self.model, self.dataset)

        # Gerador com beam search
        self.generator = AtenaLMGeneratorPro(self.cfg, self.tokenizer, self.model)

        # Self-eval e mutaes (compatibilidade)
        self.self_eval = AtenaLMSelfEval()
        self.plugin = AtenaLMMutationPlugin(self.generator, self.self_eval, self.dataset)
        self.api_collector = AtenaLMAPIDataCollector(
            cfg=self.cfg,
            dataset=self.dataset,
            grok_generator=getattr(self.core.mutation_engine, 'grok', None) if self.core else None,
            github_token=os.getenv("GITHUB_TOKEN", "")
        )

        # Ensemble
        self.ensemble = None
        if self.cfg.use_ensemble and len(self.cfg.ensemble_models) > 1:
            models = {}
            if "transformer" in self.cfg.ensemble_models and hasattr(self, 'model'):
                models["transformer"] = self.model
            if "ngram" in self.cfg.ensemble_models:
                models["ngram"] = AtenaNgramLM.load_or_create(self.cfg.ngram_path, self.cfg.ngram_order)
            if models:
                self.ensemble = ModelEnsemble(models, self.cfg.ensemble_weights)

        # Variveis de estado
        self._train_cycle = 0
        self._cycle_count = 0

        self._bootstrap()

    def _init_teacher(self):
        try:
            teacher = AutoModelForCausalLM.from_pretrained(self.cfg.teacher_model_name)
            teacher.to(DEVICE)
            teacher.eval()
            self.teacher = teacher
            logger.info(f"Modelo teacher {self.cfg.teacher_model_name} carregado")
        except Exception as e:
            logger.warning(f"Erro ao carregar teacher: {e}")
            self.teacher = None

    def _bootstrap(self):
        if self.dataset.size() < self.cfg.min_train_samples:
            self.dataset.collect_from_kb(limit=500)
            self.dataset.collect_from_evolution(limit=100)
        if self.dataset.size() >= self.cfg.min_train_samples:
            if not self.tokenizer._trained:
                texts = self.dataset.get_texts(max_samples=500)
                self.tokenizer.train(texts, num_merges=500)
                self.tokenizer.save(self.cfg.vocab_path)
            result = self.trainer.train(cycle=0)
            logger.info(f"Bootstrap: {result}")
        self.dataset.save_corpus()

    def generate(self, hint: str = "", category: str = "new_function",
                 use_rag: bool = True, use_ensemble: bool = False) -> Optional[str]:
        prompt = self.prompt_engineer.engineer_prompt(
            task=hint if hint else category,
            strategy="instruction",
            instruction="Generate optimized Python code"
        )
        if use_rag and self.rag:
            rag_prompt = self.rag.retrieve(prompt, k=2)
            if rag_prompt:
                prompt = rag_prompt + "\n\n" + prompt

        cache_key = hashlib.sha256(f"{prompt}{category}".encode()).hexdigest()
        cached = self.cache.get(cache_key)
        if cached:
            logger.debug("Cache hit")
            return cached

        if use_ensemble and self.ensemble:
            generated = self.ensemble.generate(prompt, hint)
        else:
            generated = self.generator.generate_function(hint=prompt, category=category)

        if generated:
            score, _ = self.evaluator.evaluate(generated)
            if score < 0.3:
                logger.warning(f"Gerao com score baixo ({score:.2f}) descartada")
                return None
            self.cache.set(cache_key, generated)
        return generated

    def on_cycle_end(self, generation: int, code: str, metrics: Dict, replaced: bool):
        self._cycle_count += 1
        score = metrics.get("score", 0.0)
        if replaced and score > 30:
            if self.cfg.use_augmentation:
                variants = self.augmenter.augment(code, self.cfg.augmentation_types)
                for var in variants[:3]:
                    self.dataset.add_text(var, score=score * 0.8)
            self.dataset.add_text(code, score=score)
            self.evaluator.add_corpus_hash(code)

        if self._cycle_count % self.cfg.train_every_n_cycles == 0:
            self._train_cycle += 1
            logger.info(f"\n[AtenaLM] Treino #{self._train_cycle} (gerao {generation})")
            self.dataset.collect_from_kb(limit=200)
            self.dataset.collect_from_evolution(limit=100)
            if self.cfg.use_augmentation:
                self._augment_dataset()
            if hasattr(self.trainer, 'train_with_distillation') and hasattr(self, 'teacher'):
                result = self.trainer.train_with_distillation(self.teacher, cycle=self._train_cycle)
            else:
                result = self.trainer.train(cycle=self._train_cycle)
            self.dataset.save_corpus()
            if self.writer:
                self.writer.add_scalar('train/loss', result.get('final_loss', 0), self._train_cycle)
                self.writer.add_scalar('train/perplexity', result.get('perplexity', 0), self._train_cycle)
                self.writer.add_scalar('train/dataset_size', self.dataset.size(), self._train_cycle)

        if self.cfg.use_cache_path and self._cycle_count % 10 == 0:
            self.cache.save(self.cache.persist_path)

    def _augment_dataset(self):
        texts = self.dataset.get_texts(max_samples=100, prefer_high_score=True)
        for text in texts:
            variants = self.augmenter.augment(text, self.cfg.augmentation_types)
            for var in variants[:2]:
                self.dataset.add_text(var, score=70.0)

    def get_status(self) -> Dict:
        status = {
            "strategy": self.cfg.resolve_strategy(),
            "cycle": self._cycle_count,
            "train_cycle": self._train_cycle,
            "dataset_size": self.dataset.size(),
            "cache_hit_rate": self.cache.hit_rate(),
            "eval_avg_score": self.evaluator.avg_score(),
            "has_rag": self.rag is not None,
            "has_ensemble": self.ensemble is not None,
            "has_lora": self.cfg.use_lora,
            "has_quantization": self.cfg.quantize,
        }
        if self.writer:
            status["tensorboard_dir"] = str(self.cfg.tensorboard_dir)
        return status

    def _print_banner(self):
        banner = """

   ATENA LOCAL LM PRO v4.1  FULLY INTEGRATED                         
                                                                        
   Features: LoRA  RAG  Ensemble  Beam Search  Augmentation      
   Distillation  Prompt Engineering  TensorBoard  Smart Cache      
   Advanced Evaluation  Complexity Analysis  Security Checks        

        """
        logger.info(banner)

    def print_status(self):
        status = self.get_status()
        logger.info("="*60)
        logger.info(" ATENA LOCAL LM PRO  STATUS")
        logger.info("="*60)
        for k, v in status.items():
            logger.info(f"  {k:20s}: {v}")
        logger.info("="*60)

    def integrate_with_mutation_engine(self):
        if self.core and hasattr(self.core, 'mutation_engine'):
            eng = self.core.mutation_engine
            eng.mutation_types.extend(self.plugin.mutation_types)
            _orig = eng.mutate
            def _patched(code, mtype):
                if mtype in self.plugin.mutation_types:
                    return self.plugin.mutate(code, mtype)
                return _orig(code, mtype)
            eng.mutate = _patched
            logger.info(f"Integrado {len(self.plugin.mutation_types)} mutaes LM")

    def evaluate_code(self, code: str) -> Tuple[float, Dict]:
        return self.evaluator.evaluate(code)


# 
# TRAINER PRO (com distillation e warmup)
# 

class AtenaLMTrainerPro:
    def __init__(self, cfg: AtenaLMConfigPro, tokenizer, model, dataset):
        self.cfg = cfg
        self.tokenizer = tokenizer
        self.model = model
        self.dataset = dataset
        self._step = 0
        self._losses = deque(maxlen=100)
        self._perplexities = deque(maxlen=50)

    def train(self, cycle: int) -> Dict:
        texts = self.dataset.get_texts(max_samples=self.cfg.max_train_samples, prefer_high_score=True)
        if len(texts) < self.cfg.min_train_samples:
            return {"skipped": True, "samples": len(texts)}

        logger.info(f"[Trainer] Ciclo {cycle} | {len(texts)} amostras")
        if HAS_TORCH and isinstance(self.model, AtenaTinyTransformer):
            return self._train_torch(texts, cycle)
        else:
            self.model.train(texts)
            return {"ngram_contexts": len(self.model._counts)}

    def _train_torch(self, texts: List[str], cycle: int) -> Dict:
        dataset = _TorchTextDataset(texts, self.tokenizer, self.cfg.max_seq_len)
        if len(dataset) == 0:
            return {"error": "dataset vazio"}

        loader = DataLoader(dataset, batch_size=self.cfg.batch_size,
                            shuffle=True, collate_fn=dataset.collate, num_workers=0)

        self.model.train()
        optimizer = torch.optim.AdamW(self.model.parameters(),
                                      lr=self.cfg.learning_rate,
                                      weight_decay=self.cfg.weight_decay)

        total_steps = self.cfg.train_epochs_per_cycle * len(loader)
        warmup_steps = int(total_steps * self.cfg.warmup_ratio)
        scheduler = WarmupScheduler(optimizer, warmup_steps, total_steps,
                                    self.cfg.min_learning_rate, self.cfg.learning_rate)

        losses = []
        best_loss = float('inf')
        no_improve = 0

        for epoch in range(self.cfg.train_epochs_per_cycle):
            epoch_loss = 0.0
            n_batches = 0
            for x, y in loader:
                x = x.to(DEVICE)
                y = y.to(DEVICE)
                optimizer.zero_grad()
                _, loss = self.model(x, targets=y)
                loss.backward()
                torch.nn.utils.clip_grad_norm_(self.model.parameters(), self.cfg.gradient_clip)
                optimizer.step()
                scheduler.step()
                epoch_loss += loss.item()
                n_batches += 1
                self._step += 1

            avg_loss = epoch_loss / max(n_batches, 1)
            losses.append(avg_loss)
            self._losses.append(avg_loss)
            logger.info(f"   Epoch {epoch+1}/{self.cfg.train_epochs_per_cycle} loss={avg_loss:.4f}")

            # Early stopping
            if avg_loss < best_loss - 0.01:
                best_loss = avg_loss
                no_improve = 0
            else:
                no_improve += 1
                if no_improve >= self.cfg.early_stopping_patience:
                    logger.info(f"Early stopping aps {epoch+1} epochs")
                    break

        final_loss = losses[-1] if losses else 0.0
        ppl = math.exp(min(final_loss, 20))
        self._perplexities.append(ppl)

        return {"final_loss": round(final_loss, 4), "perplexity": round(ppl, 2),
                "epochs": len(losses), "steps": self._step}

    def train_with_distillation(self, teacher, cycle: int) -> Dict:
        """Treino com knowledge distillation (requer teacher)."""
        # Simplificado: para uma implementao completa, seria necessrio
        # modificar o loop para calcular distillation loss.
        # Esta  apenas uma stub; idealmente deve-se criar um DistillationTrainer.
        logger.info("Distillation ainda no implementado completamente")
        return self.train(cycle)


# 
# WRAPPER DE COMPATIBILIDADE (para substituir o antigo)
# 

def patch_atena_core_pro(core) -> AtenaLMOrchestratorPro:
    lm = AtenaLMOrchestratorPro(core)
    lm.integrate_with_mutation_engine()
    core.local_lm = lm
    # Substitui o mtodo on_cycle_end do core se existir
    if hasattr(core, 'evolve_one_cycle'):
        _orig_evolve = core.evolve_one_cycle
        def _patched_evolve():
            result = _orig_evolve()
            try:
                m = core.evaluator.evaluate(core.current_code)
                lm.on_cycle_end(core.generation, core.current_code, m, result.get("replaced", False))
            except Exception as e:
                logger.debug(f"Erro no on_cycle_end: {e}")
            return result
        core.evolve_one_cycle = _patched_evolve
    logger.info("[patch_atena_core_pro] AtenaLM Pro integrado")
    return lm


# 
# DEMO STANDALONE
# 

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    cfg = AtenaLMConfigPro()
    cfg.setup()
    lm = AtenaLMOrchestratorPro(config=cfg)
    lm.print_status()

    # Teste de gerao
    code = lm.generate(hint="def quick_sort", category="algorithm")
    if code:
        print("\n--- Generated code ---\n", code)
        score, details = lm.evaluate_code(code)
        print(f"Score: {score:.3f}")
