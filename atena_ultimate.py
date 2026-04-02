#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
                ATENA NEURAL v4.1 - ULTIMATE EDITION (LEAN)
  LLM leve (phi-2) | PEFT (LoRA) | Hybrid RAG | Decodificao avanada
  Otimizado para GitHub Actions (CPU, baixa memria)
"""

import os
import sys
import json
import time
import random
import logging
import sqlite3
import threading
import subprocess
import tempfile
import shutil
import hashlib
import pickle
import re
import ast
import math
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Callable
from dataclasses import dataclass, field
from collections import defaultdict, deque

# =============================================================================
# IMPORTAES OBRIGATRIAS (TORCH  ESSENCIAL)
# =============================================================================
try:
    import torch
    import torch.nn.functional as F
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False
    logging.warning("PyTorch no instalado. Motor ultimate ter funcionalidade reduzida.")

# =============================================================================
# 1. CONFIGURAO ULTRA (LEAN)
# =============================================================================

@dataclass
class UltraConfig:
    BASE_DIR: Path = Path("./atena_evolution")
    MODEL_DIR: Path = BASE_DIR / "models"
    CACHE_DIR: Path = BASE_DIR / "cache"

    # LLM leve (padro: phi-2, excelente para cdigo e pequeno)
    use_llm: bool = True
    llm_model_name: str = os.getenv("LLM_MODEL_NAME", "microsoft/phi-2")
    llm_quantization: str = "none"      # Desativado para CPU (mais rpido)
    llm_device: str = "cpu"             # Fora CPU no CI
    llm_max_length: int = 512           # Menor para velocidade

    # PEFT (opcional, mas leve)
    use_peft: bool = False               # Desligado para evitar overhead
    peft_method: str = "lora"
    lora_r: int = 8
    lora_alpha: int = 16

    # RAG (desligado por padro para CI, pois exige sentence-transformers)
    use_rag: bool = False
    rag_dense_model: str = "BAAI/bge-small-en-v1.5"
    rag_use_bm25: bool = False
    rag_reranker: str = ""
    rag_top_k: int = 3

    # Decodificao simples (mais rpida)
    decoding_strategy: str = "beam"      # beam, contrastive, typical, diverse_beam
    temperature: float = 0.7
    top_p: float = 0.9
    contrastive_penalty: float = 0.5
    typical_mass: float = 0.9
    num_beams: int = 3                   # Reduzido
    diversity_penalty: float = 0.5

    # Avaliao (desligar codebleu no CI para evitar dependncias)
    evaluate_codebleu: bool = False
    evaluate_pass_at_k: int = 1
    sandbox_type: str = "subprocess"    # fallback para subprocess (mais leve)

    # Distillation (desligado)
    use_distillation: bool = False
    teacher_model: str = ""
    distillation_temperature: float = 4.0

    # Monitoramento (desligado para CI)
    use_mlflow: bool = False
    use_wandb: bool = False
    mlflow_experiment: str = "atena_neural"

    use_optuna: bool = False
    optuna_n_trials: int = 10

    cache_backend: str = "memory"
    redis_url: str = ""

    def __post_init__(self):
        for d in [self.BASE_DIR, self.MODEL_DIR, self.CACHE_DIR]:
            d.mkdir(parents=True, exist_ok=True)

cfg = UltraConfig()

# =============================================================================
# 2. SANDBOX SEGURO (subprocess mais leve)
# =============================================================================

class SecureSandbox:
    def __init__(self):
        self.timeout = 10
        self.memory_mb = 512

    def execute(self, code: str, input_data: str = "") -> Tuple[bool, str, float]:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code)
            fname = f.name
        start = time.time()
        try:
            proc = subprocess.run(
                [sys.executable, fname],
                input=input_data,
                capture_output=True,
                text=True,
                timeout=self.timeout
            )
            elapsed = time.time() - start
            return proc.returncode == 0, proc.stdout + proc.stderr, elapsed
        except subprocess.TimeoutExpired:
            return False, f"Timeout {self.timeout}s", self.timeout
        finally:
            try:
                os.unlink(fname)
            except:
                pass

# =============================================================================
# 3. RAG HBRIDO (desabilitado por padro, mantido para compatibilidade)
# =============================================================================

class HybridRAG:
    def __init__(self):
        self.corpus = []

    def add_documents(self, docs: List[str]):
        self.corpus.extend(docs)

    def retrieve(self, query: str, top_k: int = None) -> List[Tuple[str, float]]:
        return []

# =============================================================================
# 4. GERADOR AVANADO (compatvel com fallback)
# =============================================================================

class AdvancedGenerator:
    def __init__(self, model, tokenizer):
        if not HAS_TORCH:
            raise RuntimeError("PyTorch necessrio")
        self.model = model
        self.tokenizer = tokenizer

    @torch.no_grad()
    def generate(self, prompt: str, max_new_tokens: int = 256) -> str:
        inputs = self.tokenizer(prompt, return_tensors="pt", truncation=True, max_length=512).to(self.model.device)
        if cfg.decoding_strategy == "beam":
            output = self.model.generate(
                inputs.input_ids,
                max_new_tokens=max_new_tokens,
                temperature=cfg.temperature,
                top_p=cfg.top_p,
                num_beams=cfg.num_beams,
                repetition_penalty=1.2,
                do_sample=True
            )
        else:
            # fallback simples
            output = self.model.generate(inputs.input_ids, max_new_tokens=max_new_tokens)
        return self.tokenizer.decode(output[0], skip_special_tokens=True)

# =============================================================================
# 5. AVALIADOR DE CDIGO (simples)
# =============================================================================

class CodeEvaluator:
    def __init__(self):
        self.sandbox = SecureSandbox()

    def security_scan(self, code: str) -> bool:
        dangerous = [r'os\.system', r'subprocess\.call', r'eval\(', r'exec\(', r'__import__\(']
        return not any(re.search(p, code) for p in dangerous)

# =============================================================================
# 6. DUMMY MUTATION ENGINE (compatvel com main.py)
# =============================================================================

class DummyMutationEngine:
    def __init__(self):
        self.grok = None
        self.mutation_types = ["add_comment", "rename_var", "add_docstring"]

    def mutate(self, code: str, mutation_type: str) -> Tuple[str, str]:
        return code, f"Dummy: {mutation_type}"

    def generate_candidates(self, code: str, mutation_types: List[str], n: int = None) -> List:
        return []

class DummyLearner:
    def start(self): pass
    def stop(self): pass

class DummyNewsClient:
    def update_objectives(self): pass

class DummyPredictor:
    def train(self): pass

class DummyLanguageTrainer: pass
class DummyVocabularyHarvester:
    def start(self): pass
    def stop(self): pass
class DummyEpisodicMemory: pass
class DummyRewardSystem: pass
class DummyFeedbackLoop: pass

# =============================================================================
# 7. ORQUESTRADOR PRINCIPAL (LEAN)
# =============================================================================

class AtenaUltimateCore:
    def __init__(self, problem=None):
        self.cfg = cfg
        self.problem = problem
        self._init_llm()
        self.evaluator = CodeEvaluator()
        self.generator = AdvancedGenerator(self.model, self.tokenizer) if (cfg.use_llm and HAS_TORCH and self.model is not None) else None
        self.kb = self._init_kb()
        self.mutation_engine = DummyMutationEngine()
        self.current_code = self._load_current_code()
        self.best_score = self._evaluate(self.current_code)["score"]
        self.generation = 0
        self.original_code = self.current_code
        self.engine_path = cfg.BASE_DIR / "code" / "atena_engine.py"

        # Atributos de compatibilidade
        self.learner = DummyLearner()
        self.news = DummyNewsClient()
        self.predictor = DummyPredictor()
        self.lang_trainer = DummyLanguageTrainer()
        self.vocab_harvester = DummyVocabularyHarvester()
        self.episodic_memory = DummyEpisodicMemory()
        self.reward_system = DummyRewardSystem()
        self.feedback_loop = DummyFeedbackLoop()
        self.v3 = None

        # RAG desabilitado
        self.rag = None

    def _init_llm(self):
        if not cfg.use_llm or not HAS_TORCH:
            self.model = None
            self.tokenizer = None
            return

        # Tenta ler modelo de varivel de ambiente ou arquivo
        model_name = cfg.llm_model_name
        if os.path.exists(".llm_model_name"):
            with open(".llm_model_name") as f:
                model_name = f.read().strip()

        from transformers import AutoModelForCausalLM, AutoTokenizer

        try:
            logging.info(f"Carregando modelo LLM: {model_name}")
            self.model = AutoModelForCausalLM.from_pretrained(
                model_name,
                device_map="cpu",
                trust_remote_code=True,
                low_cpu_mem_usage=True,
                torch_dtype=torch.float32
            )
            self.tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
            if self.tokenizer.pad_token is None:
                self.tokenizer.pad_token = self.tokenizer.eos_token
            self.model.eval()
            logging.info(" LLM carregado com sucesso")
        except Exception as e:
            logging.error(f"Falha ao carregar LLM: {e}")
            self.model = None
            self.tokenizer = None

    def _init_kb(self):
        conn = sqlite3.connect(str(cfg.BASE_DIR / "knowledge.db"), check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _load_current_code(self) -> str:
        code_file = cfg.BASE_DIR / "code" / "atena_current.py"
        if code_file.exists():
            return code_file.read_text()
        return "def main():\n    print('Atena v4')\n"

    def _evaluate(self, code: str) -> Dict:
        if not self.evaluator.security_scan(code):
            return {"score": 0.0, "valid": False}
        success, output, exec_time = SecureSandbox().execute(code)
        if not success:
            return {"score": 0.0, "valid": False, "runtime_error": output}
        lines = len(code.splitlines())
        score = min(100, max(0, 100 - lines/10 + exec_time*5))
        return {"score": round(score, 2), "valid": True, "lines": lines, "exec_time": exec_time}

    def generate_code(self, prompt: str) -> str:
        if self.generator:
            try:
                return self.generator.generate(prompt)
            except Exception as e:
                logging.warning(f"Erro na gerao: {e}")
        return f"def {prompt.replace(' ', '_')}():\n    return 0\n"

    def evolve_one_cycle(self) -> Dict:
        self.generation += 1
        prompt = f"Write a Python function that {random.choice(['sorts a list', 'computes fibonacci', 'checks prime'])}"
        new_code = self.generate_code(prompt)
        metrics = self._evaluate(new_code)
        score = metrics["score"]
        replaced = score > self.best_score
        if replaced:
            self.best_score = score
            self.current_code = new_code
            code_file = cfg.BASE_DIR / "code" / "atena_current.py"
            code_file.parent.mkdir(parents=True, exist_ok=True)
            code_file.write_text(new_code)
        logging.info(f"Gen {self.generation}: score={score:.2f} best={self.best_score:.2f}")
        return {"generation": self.generation, "score": score, "replaced": replaced}

    def train_distillation(self, teacher_model_name: str):
        pass

# =============================================================================
# 8. INTEGRAO (patch)
# =============================================================================

def patch_atena_core(original_core) -> AtenaUltimateCore:
    new_core = AtenaUltimateCore(problem=getattr(original_core, 'problem', None))
    original_core.__class__ = type('PatchedCore', (original_core.__class__,), {})
    original_core.ultra = new_core
    def evolve_one_cycle(self):
        return new_core.evolve_one_cycle()
    def generate_code(self, prompt):
        return new_core.generate_code(prompt)
    original_core.evolve_one_cycle = evolve_one_cycle.__get__(original_core)
    original_core.generate_code = generate_code.__get__(original_core)
    return new_core

# =============================================================================
# 9. TESTE
# =============================================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    core = AtenaUltimateCore()
    for _ in range(3):
        res = core.evolve_one_cycle()
        print(res)
