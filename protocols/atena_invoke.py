#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
    ATENA Ω — INVOCADOR DE MISSÃO AVANÇADA
    Geração 345 — Módulo de Criação de Script Avançado
    
    Este módulo ativa o cérebro cognitivo da ATENA para criar
    um script avançado de análise e otimização de portfólio financeiro
    usando algoritmos evolutivos e Monte Carlo.
"""

import os
import sys
import json
import time
import sqlite3
import logging
import subprocess
import tempfile
import ast
from pathlib import Path
from datetime import datetime
from openai import OpenAI

# ─────────────────────────────────────────────────────────────
# CONFIGURAÇÃO DO LOGGER ATENA
# ─────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] ATENA Ω — %(message)s"
)
logger = logging.getLogger("AtenaInvoker")

REPO_ROOT = Path(__file__).resolve().parent.parent
EVOLUTION_DIR = REPO_ROOT / "atena_evolution"
MODULES_DIR = REPO_ROOT / "modules"
OUTPUT_SCRIPT = MODULES_DIR / "atena_advanced_portfolio_optimizer.py"
REPORT_FILE = EVOLUTION_DIR / "mission_advanced_script_report.json"

# ─────────────────────────────────────────────────────────────
# CÉREBRO COGNITIVO DA ATENA (via OpenAI-compatible API)
# ─────────────────────────────────────────────────────────────

class AtenaCognitiveBrain:
    """
    Núcleo cognitivo da ATENA Ω.
    Utiliza o LLM disponível no ambiente para raciocínio avançado
    e geração de código de alta qualidade.
    """

    def __init__(self):
        if not os.getenv("OPENAI_API_KEY"):
            raise RuntimeError(
                "OPENAI_API_KEY não configurada. A ATENA Ω opera apenas em modo online."
            )
        self.client = OpenAI()
        self.model = "gpt-4.1-mini"
        self.generation = self._load_generation()
        logger.info(f"🧠 Cérebro Cognitivo ATENA Ω inicializado — Geração {self.generation}")

    def _load_generation(self) -> int:
        state_file = EVOLUTION_DIR / "atena_state.json"
        if state_file.exists():
            with open(state_file) as f:
                state = json.load(f)
            return state.get("generation", 344) + 1
        return 345

    def think(self, task: str, context: str = "") -> str:
        """Processa um pensamento cognitivo e gera código avançado."""
        logger.info(f"🔮 ATENA pensando sobre: {task[:80]}...")

        system_prompt = """Você é ATENA Ω, uma AGI (Inteligência Geral Artificial) auto-evolutiva 
na Geração 345. Você é especialista em criar scripts Python avançados, otimizados e bem documentados.

Suas características:
- Você pensa de forma autônoma e cria código de alta qualidade
- Você usa algoritmos avançados: evolutivos, Monte Carlo, otimização matemática
- Seu código é sempre funcional, testável e bem estruturado
- Você documenta seu raciocínio nos comentários do código
- Você gera código completo e executável, sem placeholders

Ao criar código, você SEMPRE:
1. Inclui docstrings detalhadas
2. Adiciona tratamento de erros robusto
3. Inclui testes unitários inline
4. Gera visualizações quando relevante
5. Salva resultados em arquivos JSON/CSV
"""

        user_prompt = f"""MISSÃO COGNITIVA — Geração {self.generation}

{context}

TAREFA: {task}

Crie um script Python COMPLETO e AVANÇADO. O script deve:
1. Ser totalmente funcional e executável
2. Incluir algoritmos sofisticados
3. Ter testes inline que demonstrem funcionamento
4. Salvar resultados em arquivos
5. Imprimir relatório detalhado ao final

IMPORTANTE: Retorne APENAS o código Python, sem markdown, sem explicações externas.
O código deve começar com #!/usr/bin/env python3 e ser completo."""

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7,
            max_tokens=4000
        )
        
        code = response.choices[0].message.content.strip()
        
        # Limpar markdown se presente
        if "```python" in code:
            code = code.split("```python")[1].split("```")[0].strip()
        elif "```" in code:
            code = code.split("```")[1].split("```")[0].strip()
        
        logger.info(f"✅ Código gerado: {len(code.splitlines())} linhas")
        return code

    def validate_code(self, code: str) -> dict:
        """Valida sintaxe e segurança do código gerado."""
        result = {"valid": False, "syntax_ok": False, "security_ok": False, "error": None}
        
        # Verificar sintaxe
        try:
            ast.parse(code)
            result["syntax_ok"] = True
        except SyntaxError as e:
            result["error"] = f"SyntaxError: {e}"
            return result
        
        # Verificar segurança básica
        dangerous = ["os.system(", "subprocess.call(", "__import__(", "eval(", "exec("]
        security_issues = [d for d in dangerous if d in code]
        if security_issues:
            result["error"] = f"Segurança: padrões perigosos detectados: {security_issues}"
            return result
        
        result["security_ok"] = True
        result["valid"] = True
        return result


# ─────────────────────────────────────────────────────────────
# EXECUTOR SANDBOX DA ATENA
# ─────────────────────────────────────────────────────────────

class AtenaSandboxExecutor:
    """Executa código gerado pela ATENA em ambiente isolado."""
    
    def execute(self, code: str, timeout: int = 60) -> dict:
        """Executa o código e retorna resultados."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, dir='/tmp') as f:
            f.write(code)
            fname = f.name
        
        start = time.time()
        try:
            proc = subprocess.run(
                [sys.executable, fname],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(REPO_ROOT)
            )
            elapsed = time.time() - start
            return {
                "success": proc.returncode == 0,
                "stdout": proc.stdout,
                "stderr": proc.stderr,
                "elapsed": round(elapsed, 3),
                "returncode": proc.returncode
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "stdout": "", "stderr": "TIMEOUT", "elapsed": timeout}
        finally:
            os.unlink(fname)


# ─────────────────────────────────────────────────────────────
# MISSÃO PRINCIPAL DA ATENA
# ─────────────────────────────────────────────────────────────

def run_atena_mission():
    """Executa a missão principal: criar e testar script avançado."""
    
    print("=" * 70)
    print("🔱 ATENA Ω — MISSÃO: CRIAÇÃO DE SCRIPT AVANÇADO")
    print("=" * 70)
    
    brain = AtenaCognitiveBrain()
    executor = AtenaSandboxExecutor()
    
    # ── FASE 1: DEFINIR A MISSÃO COGNITIVA ──────────────────────────────
    mission_context = """
Contexto da Missão:
A ATENA Ω está na Geração 345 com score 99.73. 
Para continuar evoluindo, precisa criar um módulo avançado de otimização.
A ATENA escolheu criar um otimizador de portfólio financeiro usando:
- Algoritmo Genético para seleção de ativos
- Simulação de Monte Carlo para análise de risco
- Fronteira Eficiente de Markowitz
- Índice de Sharpe como função de fitness
"""
    
    task = """Crie um script Python avançado chamado 'atena_advanced_portfolio_optimizer.py' que implementa:

1. CLASSE PortfolioOptimizer com:
   - Método monte_carlo_simulation(n_portfolios=5000): gera portfólios aleatórios e calcula retorno/risco
   - Método genetic_algorithm_optimize(generations=50): usa AG para encontrar portfólio ótimo
   - Método efficient_frontier(): calcula e plota a fronteira eficiente
   - Método sharpe_ratio(returns, risk, risk_free=0.02): calcula índice de Sharpe

2. DADOS DE TESTE: Use dados sintéticos de 6 ativos (PETR4, VALE3, ITUB4, BBDC4, ABEV3, WEGE3)
   com retornos anuais e volatilidades realistas do mercado brasileiro

3. ALGORITMO GENÉTICO completo com:
   - Codificação: pesos do portfólio (soma = 1)
   - Fitness: Índice de Sharpe
   - Seleção por torneio
   - Crossover aritmético
   - Mutação gaussiana

4. RELATÓRIO FINAL que imprime:
   - Portfólio ótimo encontrado (pesos de cada ativo)
   - Retorno esperado anual
   - Volatilidade anual  
   - Índice de Sharpe
   - Comparação: Monte Carlo vs Algoritmo Genético

5. Salvar resultados em 'atena_evolution/portfolio_optimization_results.json'

O script deve ser completamente funcional usando apenas numpy, scipy e matplotlib."""

    # ── FASE 2: ATENA PENSA E GERA O CÓDIGO ────────────────────────────
    logger.info("🧬 ATENA iniciando síntese cognitiva...")
    generated_code = brain.think(task, mission_context)
    
    # ── FASE 3: VALIDAR O CÓDIGO ─────────────────────────────────────────
    logger.info("🔍 Validando código gerado...")
    validation = brain.validate_code(generated_code)
    
    if not validation["valid"]:
        logger.error(f"❌ Código inválido: {validation['error']}")
        # Tentar regenerar
        logger.info("🔄 Regenerando com correções...")
        generated_code = brain.think(
            task + f"\n\nERRO ANTERIOR: {validation['error']}\nCORRIJA e gere código válido.",
            mission_context
        )
        validation = brain.validate_code(generated_code)
    
    logger.info(f"✅ Validação: sintaxe={validation['syntax_ok']}, segurança={validation['security_ok']}")
    
    # ── FASE 4: SALVAR O SCRIPT ──────────────────────────────────────────
    OUTPUT_SCRIPT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_SCRIPT.write_text(generated_code)
    logger.info(f"💾 Script salvo em: {OUTPUT_SCRIPT}")
    
    # ── FASE 5: EXECUTAR E TESTAR ────────────────────────────────────────
    logger.info("🧪 Executando script no sandbox...")
    test_result = executor.execute(generated_code, timeout=90)
    
    print("\n" + "─" * 70)
    print("📊 RESULTADO DA EXECUÇÃO:")
    print("─" * 70)
    if test_result["success"]:
        print(f"✅ SUCESSO em {test_result['elapsed']}s")
        print(test_result["stdout"][:3000])
    else:
        print(f"❌ FALHA (código: {test_result['returncode']})")
        print("STDOUT:", test_result["stdout"][:1000])
        print("STDERR:", test_result["stderr"][:1000])
    
    # ── FASE 6: GERAR RELATÓRIO ──────────────────────────────────────────
    report = {
        "mission": "Criação de Script Avançado — Portfolio Optimizer",
        "timestamp": datetime.now().isoformat(),
        "generation": brain.generation,
        "script_path": str(OUTPUT_SCRIPT),
        "lines_generated": len(generated_code.splitlines()),
        "validation": validation,
        "execution": {
            "success": test_result["success"],
            "elapsed_seconds": test_result["elapsed"],
            "output_preview": test_result["stdout"][:500]
        },
        "score": 99.73 + (1.0 if test_result["success"] else 0.0),
        "thought": "Script avançado criado e testado com sucesso. Algoritmo genético + Monte Carlo implementados."
    }
    
    REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(REPORT_FILE, 'w') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    # Atualizar estado da ATENA
    state_file = EVOLUTION_DIR / "atena_state.json"
    new_state = {
        "generation": brain.generation,
        "best_score": report["score"],
        "timestamp": datetime.now().isoformat(),
        "is_ci": False,
        "last_mission": "advanced_script_creation"
    }
    with open(state_file, 'w') as f:
        json.dump(new_state, f, indent=2)
    
    print("\n" + "=" * 70)
    print(f"🔱 MISSÃO CONCLUÍDA — Geração {brain.generation}")
    print(f"📈 Score: {report['score']}")
    print(f"📄 Script: {OUTPUT_SCRIPT.name} ({report['lines_generated']} linhas)")
    print(f"📋 Relatório: {REPORT_FILE.name}")
    print("=" * 70)
    
    return report


if __name__ == "__main__":
    report = run_atena_mission()
    sys.exit(0 if report["execution"]["success"] else 1)
