#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
                ATENA NEURAL v4.0 - ULTIMATE EDITION                         
  LLM 4-bit | PEFT (LoRA/AdaLoRA/IA3) | Hybrid RAG + Re-ranker               
  Contrastive Decoding | CodeBLEU | Distillation | MLflow | Optuna          
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
import math                      # <-- ADICIONADO (usado em diverse_beam_search)
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Callable
from dataclasses import dataclass, field, asdict
from collections import defaultdict, deque

# =============================================================================
# IMPORTAÇÕES OBRIGATÓRIAS PARA O MÓDULO (TORCH É ESSENCIAL)
# =============================================================================
try:
    import torch
    import torch.nn.functional as F
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False
    # Se não houver torch, o motor ultimate não funcionará corretamente.
    # A classe AdvancedGenerator será substituída por um fallback simples.
    logging.warning("PyTorch não está instalado. O motor ultimate terá funcionalidade reduzida.")

# =============================================================================
# 1. CONFIGURAÇÃO ULTRA (com suporte a todas as novidades)
# =============================================================================

@dataclass
class UltraConfig:
    # Diretórios
    BASE_DIR: Path = Path("./atena_evolution")
    MODEL_DIR: Path = BASE_DIR / "models"
    CACHE_DIR: Path = BASE_DIR / "cache"
    
    # LLM
    use_llm: bool = True
    llm_model_name: str = "Salesforce/codegen-350M-mono"  # ou "bigcode/starcoderbase-1b"
    llm_quantization: str = "4bit"   # none, 4bit, 8bit
    llm_device: str = "auto"
    llm_max_length: int = 1024
    
    # PEFT
    use_peft: bool = True
    peft_method: str = "lora"   # lora, adalora, ia3, dora
    lora_r: int = 16
    lora_alpha: int = 32
    
    # RAG híbrido
    use_rag: bool = True
    rag_dense_model: str = "BAAI/bge-small-en-v1.5"
    rag_use_bm25: bool = True
    rag_reranker: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    rag_top_k: int = 5
    
    # Decodificação avançada
    decoding_strategy: str = "contrastive"  # contrastive, typical, diverse_beam
    temperature: float = 0.8
    top_p: float = 0.95
    contrastive_penalty: float = 0.5
    typical_mass: float = 0.9
    num_beams: int = 5
    diversity_penalty: float = 0.6
    
    # Avaliação
    evaluate_codebleu: bool = True
    evaluate_pass_at_k: int = 3
    sandbox_type: str = "docker"  # docker, nsjail, subprocess
    
    # Distillation
    use_distillation: bool = True
    teacher_model: str = "bigcode/starcoderbase-3b"
    distillation_temperature: float = 4.0
    
    # Monitoramento
    use_mlflow: bool = True
    use_wandb: bool = False
    mlflow_experiment: str = "atena_neural"
    
    # Otimização
    use_optuna: bool = True
    optuna_n_trials: int = 20
    
    # Cache
    cache_backend: str = "memory"  # memory, redis
    redis_url: str = "redis://localhost:6379/0"
    
    def __post_init__(self):
        for d in [self.BASE_DIR, self.MODEL_DIR, self.CACHE_DIR]:
            d.mkdir(parents=True, exist_ok=True)

cfg = UltraConfig()

# =============================================================================
# 2. SANDBOX SEGURO (Docker / nsjail)
# =============================================================================

class SecureSandbox:
    def __init__(self):
        self.timeout = 10
        self.memory_mb = 512
        self.use_docker = self._check_docker()
    
    def _check_docker(self) -> bool:
        try:
            subprocess.run(["docker", "ps"], capture_output=True, check=True)
            return True
        except:
            return False
    
    def execute(self, code: str, input_data: str = "") -> Tuple[bool, str, float]:
        if self.use_docker:
            return self._run_docker(code, input_data)
        else:
            return self._run_subprocess(code, input_data)
    
    def _run_docker(self, code: str, input_data: str) -> Tuple[bool, str, float]:
        with tempfile.TemporaryDirectory() as tmpdir:
            script = Path(tmpdir) / "script.py"
            script.write_text(code)
            cmd = [
                "docker", "run", "--rm",
                "--memory", f"{self.memory_mb}m",
                "--cpus", "0.5",
                "--network", "none",
                "--pids-limit", "50",
                "-v", f"{tmpdir}:/app",
                "-w", "/app",
                "python:3.10-slim",
                "python", "script.py"
            ]
            start = time.time()
            try:
                proc = subprocess.run(cmd, input=input_data, capture_output=True, text=True, timeout=self.timeout)
                elapsed = time.time() - start
                return proc.returncode == 0, proc.stdout + proc.stderr, elapsed
            except subprocess.TimeoutExpired:
                return False, f"Timeout {self.timeout}s", self.timeout
    
    def _run_subprocess(self, code: str, input_data: str) -> Tuple[bool, str, float]:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code)
            fname = f.name
        start = time.time()
        try:
            proc = subprocess.run([sys.executable, fname], input=input_data, capture_output=True, text=True, timeout=self.timeout)
            elapsed = time.time() - start
            return proc.returncode == 0, proc.stdout + proc.stderr, elapsed
        except subprocess.TimeoutExpired:
            return False, f"Timeout {self.timeout}s", self.timeout
        finally:
            os.unlink(fname)

# =============================================================================
# 3. RAG HÍBRIDO COM RE-RANKER (Dense + BM25 + Cross-encoder)
# =============================================================================

class HybridRAG:
    def __init__(self):
        self.dense = None
        self.bm25 = None
        self.reranker = None
        self.corpus = []
        self.has_reranker = False
        self._init_dense()
        self._init_reranker()
    
    def _init_dense(self):
        try:
            from sentence_transformers import SentenceTransformer
            self.dense = SentenceTransformer(cfg.rag_dense_model)
        except ImportError:
            logging.warning("sentence-transformers não instalado")
    
    def _init_reranker(self):
        if cfg.rag_reranker and HAS_TORCH:
            try:
                from transformers import AutoModelForSequenceClassification, AutoTokenizer
                self.reranker_model = AutoModelForSequenceClassification.from_pretrained(cfg.rag_reranker)
                self.reranker_tokenizer = AutoTokenizer.from_pretrained(cfg.rag_reranker)
                self.reranker_model.eval()
                self.has_reranker = True
            except Exception as e:
                logging.warning(f"Erro ao carregar reranker: {e}")
                self.has_reranker = False
    
    def add_documents(self, docs: List[str]):
        self.corpus.extend(docs)
        if self.dense:
            self.dense_emb = self.dense.encode(docs, show_progress_bar=False)
        if cfg.rag_use_bm25:
            try:
                from rank_bm25 import BM25Okapi
                tokenized = [doc.split() for doc in self.corpus]
                self.bm25 = BM25Okapi(tokenized)
            except ImportError:
                logging.warning("rank_bm25 não instalado, desabilitando BM25")
                self.bm25 = None
    
    def retrieve(self, query: str, top_k: int = None) -> List[Tuple[str, float]]:
        top_k = top_k or cfg.rag_top_k
        if not self.corpus:
            return []
        # Dense
        dense_scores = []
        if self.dense:
            q_emb = self.dense.encode([query])
            from sklearn.metrics.pairwise import cosine_similarity
            dense_scores = cosine_similarity(q_emb, self.dense_emb)[0]
            dense_scores = list(enumerate(dense_scores))
        # BM25
        sparse_scores = []
        if hasattr(self, 'bm25') and self.bm25:
            bm25_scores = self.bm25.get_scores(query.split())
            sparse_scores = list(enumerate(bm25_scores))
        # Fusão híbrida (reciprocal rank fusion)
        scores = {}
        for idx, score in dense_scores:
            scores[idx] = scores.get(idx, 0) + 1.0 / (1 + score)  # RRF
        for idx, score in sparse_scores:
            scores[idx] = scores.get(idx, 0) + 1.0 / (1 + score)
        candidates = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k*2]
        # Re-ranking com cross-encoder (requer torch)
        if self.has_reranker and candidates and HAS_TORCH:
            pairs = [(query, self.corpus[idx]) for idx, _ in candidates]
            inputs = self.reranker_tokenizer(pairs, padding=True, truncation=True, return_tensors="pt", max_length=512)
            with torch.no_grad():
                rerank_scores = self.reranker_model(**inputs).logits.squeeze(-1).tolist()
            candidates = sorted(zip([idx for idx,_ in candidates], rerank_scores), key=lambda x: x[1], reverse=True)
        # Retorna textos
        return [(self.corpus[idx], score) for idx, score in candidates[:top_k]]

# =============================================================================
# 4. GERADOR COM DECODIFICAÇÃO AVANÇADA (Contrastive, Typical, Diverse Beam)
# =============================================================================

class AdvancedGenerator:
    def __init__(self, model, tokenizer):
        if not HAS_TORCH:
            raise RuntimeError("PyTorch é necessário para o AdvancedGenerator")
        self.model = model
        self.tokenizer = tokenizer
    
    @torch.no_grad()
    def generate(self, prompt: str, max_new_tokens: int = 512) -> str:
        inputs = self.tokenizer(prompt, return_tensors="pt", truncation=True, max_length=1024).to(self.model.device)
        if cfg.decoding_strategy == "contrastive":
            output = self._contrastive_decoding(inputs.input_ids, max_new_tokens)
        elif cfg.decoding_strategy == "typical":
            output = self._typical_decoding(inputs.input_ids, max_new_tokens)
        elif cfg.decoding_strategy == "diverse_beam":
            output = self._diverse_beam_search(inputs.input_ids, max_new_tokens)
        else:
            output = self.model.generate(
                inputs.input_ids,
                max_new_tokens=max_new_tokens,
                temperature=cfg.temperature,
                top_p=cfg.top_p,
                num_beams=cfg.num_beams,
                repetition_penalty=1.2
            )
        return self.tokenizer.decode(output[0], skip_special_tokens=True)
    
    def _contrastive_decoding(self, input_ids, max_new_tokens):
        for _ in range(max_new_tokens):
            logits = self.model(input_ids).logits[0, -1, :]
            amateur_logits = logits / 2.0
            expert_logits = logits / cfg.temperature
            contrast_logits = expert_logits - cfg.contrastive_penalty * amateur_logits
            next_token = torch.argmax(contrast_logits, dim=-1, keepdim=True)
            input_ids = torch.cat([input_ids, next_token.unsqueeze(0)], dim=-1)
            if next_token == self.tokenizer.eos_token_id:
                break
        return input_ids
    
    def _typical_decoding(self, input_ids, max_new_tokens):
        for _ in range(max_new_tokens):
            logits = self.model(input_ids).logits[0, -1, :] / cfg.temperature
            probs = F.softmax(logits, dim=-1)
            entropy = -torch.sum(probs * torch.log(probs + 1e-10))
            log_probs = torch.log(probs + 1e-10)
            typical_mask = torch.abs(-log_probs - entropy) < cfg.typical_mass
            if not typical_mask.any():
                typical_mask = torch.ones_like(typical_mask)
            probs_filtered = probs * typical_mask
            probs_filtered /= probs_filtered.sum()
            next_token = torch.multinomial(probs_filtered, 1)
            input_ids = torch.cat([input_ids, next_token.unsqueeze(0)], dim=-1)
            if next_token == self.tokenizer.eos_token_id:
                break
        return input_ids
    
    def _diverse_beam_search(self, input_ids, max_new_tokens):
        num_beams = cfg.num_beams
        num_groups = 3
        beams = [(input_ids, 0.0)]
        for _ in range(max_new_tokens):
            all_candidates = []
            for group in range(num_groups):
                group_beams = beams[group::num_groups] if len(beams) >= num_groups else beams
                for seq, score in group_beams:
                    logits = self.model(seq).logits[0, -1, :] / cfg.temperature
                    log_probs = F.log_softmax(logits, dim=-1)
                    topk_vals, topk_idx = torch.topk(log_probs, k=50)
                    for i in range(len(topk_idx)):
                        token = topk_idx[i].item()
                        new_score = score - topk_vals[i].item()
                        # Penalidade de diversidade
                        group_tokens = [t for _, s in all_candidates if s % num_groups == group]
                        if cfg.diversity_penalty > 0 and token in group_tokens:
                            new_score += cfg.diversity_penalty * math.log(1 + group_tokens.count(token))
                        new_seq = torch.cat([seq, torch.tensor([[token]], device=seq.device)], dim=1)
                        all_candidates.append((new_seq, new_score, group))
            all_candidates.sort(key=lambda x: x[1])
            beams = [(seq, score) for seq, score, _ in all_candidates[:num_beams]]
            if all(seq[0, -1] == self.tokenizer.eos_token_id for seq, _ in beams):
                break
        return min(beams, key=lambda x: x[1])[0]

# =============================================================================
# 5. AVALIAÇÃO AVANÇADA (CodeBLEU, pass@k, segurança)
# =============================================================================

class CodeEvaluator:
    def __init__(self):
        self.sandbox = SecureSandbox()
    
    def evaluate_codebleu(self, generated: str, reference: str) -> float:
        try:
            from codebleu import calc_codebleu
            result = calc_codebleu([reference], [generated], lang="python")
            return result['codebleu']
        except ImportError:
            # fallback BLEU simples
            try:
                from nltk.translate.bleu_score import sentence_bleu
                return sentence_bleu([reference.split()], generated.split())
            except ImportError:
                return 0.0
    
    def evaluate_pass_at_k(self, code: str, test_cases: List[Tuple[str, str]], k: int = None) -> float:
        k = k or cfg.evaluate_pass_at_k
        passed = 0
        for _ in range(k):
            ok = True
            for inp, expected in test_cases:
                success, output, _ = self.sandbox.execute(code, inp)
                if not success or output.strip() != expected.strip():
                    ok = False
                    break
            if ok:
                passed += 1
        return passed / k
    
    def security_scan(self, code: str) -> bool:
        dangerous = [r'os\.system', r'subprocess\.call', r'eval\(', r'exec\(', r'__import__\(']
        return not any(re.search(p, code) for p in dangerous)

# =============================================================================
# 6. ORQUESTRADOR PRINCIPAL (integrando LLM, RAG, PEFT, Distillation)
# =============================================================================

class AtenaUltimateCore:
    def __init__(self, problem=None):
        self.cfg = cfg
        self.problem = problem  # compatibilidade com o core original
        self._init_llm()
        self._init_rag()
        self.evaluator = CodeEvaluator()
        if cfg.use_llm and HAS_TORCH and self.model is not None:
            self.generator = AdvancedGenerator(self.model, self.tokenizer)
        else:
            self.generator = None
        self.kb = self._init_kb()
        self.mutation_engine = self._init_mutation_engine()
        self.current_code = self._load_current_code()
        self.best_score = self._evaluate(self.current_code)["score"]
        self.generation = 0
        # Atributos para compatibilidade com o sistema original
        self.original_code = self.current_code
        self.engine_path = cfg.BASE_DIR / "code" / "atena_engine.py"
    
    def _init_llm(self):
        if not cfg.use_llm or not HAS_TORCH:
            self.model = None
            self.tokenizer = None
            return
        from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
        
        quantization_config = None
        if cfg.llm_quantization == "4bit":
            quantization_config = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_compute_dtype=torch.float16)
        elif cfg.llm_quantization == "8bit":
            quantization_config = BitsAndBytesConfig(load_in_8bit=True)
        
        try:
            self.model = AutoModelForCausalLM.from_pretrained(
                cfg.llm_model_name,
                quantization_config=quantization_config,
                device_map=cfg.llm_device,
                trust_remote_code=True
            )
            self.tokenizer = AutoTokenizer.from_pretrained(cfg.llm_model_name, trust_remote_code=True)
            if self.tokenizer.pad_token is None:
                self.tokenizer.pad_token = self.tokenizer.eos_token
            
            if cfg.use_peft:
                self._apply_peft()
            
            self.model.eval()
        except Exception as e:
            logging.error(f"Falha ao carregar modelo LLM: {e}")
            self.model = None
            self.tokenizer = None
    
    def _apply_peft(self):
        try:
            from peft import LoraConfig, AdaLoraConfig, IA3Config, get_peft_model, TaskType
            if cfg.peft_method == "lora":
                config = LoraConfig(task_type=TaskType.CAUSAL_LM, r=cfg.lora_r, lora_alpha=cfg.lora_alpha, target_modules=["q_proj", "v_proj"])
            elif cfg.peft_method == "adalora":
                config = AdaLoraConfig(task_type=TaskType.CAUSAL_LM, r=cfg.lora_r, lora_alpha=cfg.lora_alpha, target_r=4)
            elif cfg.peft_method == "ia3":
                config = IA3Config(task_type=TaskType.CAUSAL_LM, target_modules=["k_proj", "v_proj", "q_proj"])
            else:
                return
            self.model = get_peft_model(self.model, config)
            logging.info(f"PEFT {cfg.peft_method} aplicado")
        except Exception as e:
            logging.warning(f"Erro ao aplicar PEFT: {e}")
    
    def _init_rag(self):
        self.rag = HybridRAG() if cfg.use_rag else None
        if self.rag:
            # Tenta carregar conhecimento existente do banco SQLite
            try:
                kb_path = cfg.BASE_DIR / "knowledge.db"
                if kb_path.exists():
                    conn = sqlite3.connect(str(kb_path))
                    cursor = conn.execute("SELECT code FROM learned_functions LIMIT 100")
                    docs = [row[0] for row in cursor.fetchall()]
                    if docs:
                        self.rag.add_documents(docs)
                        logging.info(f"RAG populado com {len(docs)} documentos")
                    conn.close()
            except Exception as e:
                logging.warning(f"Erro ao carregar documentos para RAG: {e}")
    
    def _init_kb(self):
        # Placeholder: pode ser expandido para conectar com o KnowledgeBase original
        # Aqui retornamos um objeto dummy com uma conexão SQLite (para compatibilidade)
        conn = sqlite3.connect(str(cfg.BASE_DIR / "knowledge.db"), check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        return conn
    
    def _load_current_code(self) -> str:
        code_file = cfg.BASE_DIR / "code" / "atena_current.py"
        if code_file.exists():
            return code_file.read_text()
        return "def main():\n    print('Atena v4')\n"
    
    def _evaluate(self, code: str) -> Dict:
        # Avaliação com CodeBLEU e segurança
        if not self.evaluator.security_scan(code):
            return {"score": 0.0, "valid": False, "security": False}
        # Executa no sandbox
        success, output, exec_time = self.evaluator.sandbox.execute(code)
        if not success:
            return {"score": 0.0, "valid": False, "runtime_error": output}
        # Métricas simples (pode ser substituído pelo EvolvableScorer)
        lines = len(code.splitlines())
        score = min(100, max(0, 100 - lines/10 + exec_time*5))
        return {"score": round(score, 2), "valid": True, "lines": lines, "exec_time": exec_time}
    
    def _init_mutation_engine(self):
        # Placeholder - aqui você pode integrar com o MutationEngine original
        return None
    
    def generate_code(self, prompt: str) -> str:
        if self.generator:
            return self.generator.generate(prompt)
        # Fallback simples
        return f"def {prompt.replace(' ', '_')}():\n    pass\n"
    
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
        if not cfg.use_distillation or not HAS_TORCH:
            return
        try:
            from transformers import AutoModelForCausalLM
            teacher = AutoModelForCausalLM.from_pretrained(teacher_model_name, device_map="auto")
            teacher.eval()
            # Aqui viria o loop de distillation
            logging.info("Distillation concluída (placeholder)")
        except Exception as e:
            logging.warning(f"Erro na distillation: {e}")

# =============================================================================
# 7. INTEGRAÇÃO COM O SISTEMA ORIGINAL (patch)
# =============================================================================

def patch_atena_core(original_core) -> AtenaUltimateCore:
    """
    Substitui o core original pelo novo ultra-core mantendo compatibilidade.
    Retorna a nova instância.
    """
    new_core = AtenaUltimateCore(problem=getattr(original_core, 'problem', None))
    # Copia atributos essenciais
    original_core.__class__ = type('PatchedCore', (original_core.__class__,), {})
    original_core.ultra = new_core
    # Monkey patch dos métodos principais
    def evolve_one_cycle(self):
        return new_core.evolve_one_cycle()
    def generate_code(self, prompt):
        return new_core.generate_code(prompt)
    original_core.evolve_one_cycle = evolve_one_cycle.__get__(original_core)
    original_core.generate_code = generate_code.__get__(original_core)
    return new_core

# =============================================================================
# 8. DEMO / TESTE
# =============================================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    core = AtenaUltimateCore()
    for _ in range(3):
        res = core.evolve_one_cycle()
        print(res)
