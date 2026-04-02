import operator
import logging
from typing import TypedDict, Annotated, Sequence, Optional, Dict, Any, List

from langgraph.graph import StateGraph, END
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage

# Importações dos componentes da Atena (ajuste os caminhos conforme sua estrutura)
from atena_engine import AtenaCore, Config, MutationEngine, CodeEvaluator, Sandbox, EvolvableScorer
from atena_engine import KnowledgeBase, AdaptiveChecker, MetaLearner

# Configuração de logging
logger = logging.getLogger("atena.langgraph")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s - %(message)s")

# =============================================================================
# 1. DEFINIÇÃO DO ESTADO (compatível com atena_state.json)
# =============================================================================
class AtenaState(TypedDict):
    """Estado completo da evolução, mantido pelo LangGraph."""
    messages: Annotated[Sequence[BaseMessage], operator.add]   # histórico de mensagens
    generation: int                                             # geração atual
    current_code: str                                           # código sendo evoluído
    best_code: str                                              # melhor código até agora
    best_score: float                                           # melhor score
    problem_name: Optional[str]                                 # nome do problema (se houver)
    problem_description: Optional[str]                          # descrição do problema
    mutation_history: List[Dict[str, Any]]                      # histórico de mutações aplicadas
    last_mutation: Optional[str]                                # última mutação aplicada
    last_score: float                                           # score da última avaliação
    replaced: bool                                              # se a mutação foi aceita
    error: Optional[str]                                        # último erro, se houver

# =============================================================================
# 2. FERRAMENTAS LANGCHAIN QUE CHAMAM OS COMPONENTES DA ATENA
# =============================================================================
@tool
def mutate_code(code: str, mutation_type: str, core: AtenaCore) -> str:
    """
    Aplica uma mutação ao código usando o MutationEngine da Atena.
    Retorna o código mutado ou uma mensagem de erro.
    """
    try:
        mutated, description = core.mutation_engine.mutate(code, mutation_type)
        if mutated != code:
            logger.info(f"Mutacao '{mutation_type}' aplicada: {description}")
            return mutated
        else:
            return code  # mutação não alterou
    except Exception as e:
        logger.error(f"Erro na mutação {mutation_type}: {e}")
        return code

@tool
def evaluate_in_sandbox(code: str, core: AtenaCore) -> Dict[str, Any]:
    """
    Avalia o código no sandbox da Atena e retorna um dicionário com score e detalhes.
    """
    try:
        metrics = core.evaluator.evaluate(code, original_code=core.current_code)
        # Se houver um EvolvableScorer, usamos seu score (ou o score do problema)
        score = metrics.get("score", 0.0)
        return {
            "score": score,
            "valid": metrics.get("valid", False),
            "runtime_error": metrics.get("runtime_error"),
            "complexity": metrics.get("complexity", 0),
            "num_functions": metrics.get("num_functions", 0),
            "lines": metrics.get("lines", 0),
        }
    except Exception as e:
        logger.error(f"Erro na avaliação: {e}")
        return {"score": 0.0, "error": str(e)}

# =============================================================================
# 3. NÓS DO GRAFO
# =============================================================================
def think_node(state: AtenaState, core: AtenaCore) -> Dict[str, Any]:
    """
    Nó de pensamento: decide qual mutação aplicar a seguir.
    Pode usar um LLM (ex: local LM ou Grok) para sugerir uma mutação baseada no contexto.
    """
    # Se houver um modelo de linguagem local, use-o para escolher a mutação
    if hasattr(core, 'local_lm') and core.local_lm:
        prompt = f"""
        Atualmente temos um código com score {state['best_score']:.2f}.
        Problema: {state.get('problem_name', 'Nenhum')}
        Deseja-se melhorar o código.
        Que tipo de mutação seria mais promissora? Responda apenas com o nome da mutação.
        Tipos disponíveis: {core.mutation_engine.mutation_types}
        """
        try:
            suggestion = core.local_lm.generate(prompt, max_new_tokens=20)
            # Limpa a resposta para conter apenas o nome da mutação
            mutation_type = suggestion.strip().split()[0] if suggestion else None
            if mutation_type in core.mutation_engine.mutation_types:
                chosen = mutation_type
            else:
                chosen = random.choice(core.mutation_engine.mutation_types)
        except Exception as e:
            logger.warning(f"Erro ao consultar LM: {e}")
            chosen = random.choice(core.mutation_engine.mutation_types)
    else:
        chosen = random.choice(core.mutation_engine.mutation_types)

    logger.info(f"Nó think: escolheu mutação '{chosen}'")
    # Registra a decisão como uma mensagem
    msg = HumanMessage(content=f"Vou aplicar a mutação: {chosen}")
    return {
        "messages": [msg],
        "last_mutation": chosen,
        "error": None,
    }

def mutate_node(state: AtenaState, core: AtenaCore) -> Dict[str, Any]:
    """
    Nó de mutação: aplica a mutação escolhida ao código.
    """
    mutation_type = state.get("last_mutation")
    if not mutation_type:
        return {"error": "Nenhuma mutação escolhida"}

    mutated = mutate_code.invoke({
        "code": state["current_code"],
        "mutation_type": mutation_type,
        "core": core,
    })
    if mutated == state["current_code"]:
        return {"error": f"Falha na mutação '{mutation_type}' (nenhuma alteração)"}
    else:
        logger.info(f"Nó mutate: código mutado com sucesso")
        return {"current_code": mutated, "error": None}

def test_node(state: AtenaState, core: AtenaCore) -> Dict[str, Any]:
    """
    Nó de teste: avalia o código mutado no sandbox e atualiza o estado.
    """
    code = state["current_code"]
    evaluation = evaluate_in_sandbox.invoke({"code": code, "core": core})
    score = evaluation.get("score", 0.0)
    valid = evaluation.get("valid", False)

    # Atualiza o melhor código se necessário
    replaced = False
    if valid and score > state["best_score"] + Config.MIN_IMPROVEMENT_DELTA:
        replaced = True
        best_code = code
        best_score = score
        logger.info(f"Nó test: nova melhor pontuação {score:.2f} (antes {state['best_score']:.2f})")
    else:
        best_code = state["best_code"]
        best_score = state["best_score"]

    # Registra o episódio na memória episódica (se disponível)
    if hasattr(core, 'episodic_memory'):
        core.episodic_memory.record(
            generation=state["generation"] + 1,
            mutation=state.get("last_mutation", "none"),
            score=score,
            replaced=replaced,
            metrics=evaluation,
            code_snapshot=code[:500],
        )

    # Registra métricas no banco de conhecimento
    core.kb.record_evolution(
        generation=state["generation"] + 1,
        mutation=state.get("last_mutation", "none"),
        old_score=state["best_score"],
        new_score=score,
        replaced=replaced,
        features=evaluation,
        test_results={}
    )

    return {
        "generation": state["generation"] + 1,
        "best_score": best_score,
        "best_code": best_code,
        "last_score": score,
        "replaced": replaced,
        "error": None,
        "messages": [AIMessage(content=f"Score: {score:.2f} | {'Aceita' if replaced else 'Rejeitada'}")],
    }

def should_continue(state: AtenaState) -> str:
    """
    Decide se o grafo deve continuar evoluindo ou terminar.
    Condição: se o score melhorou e ainda não atingimos o limite de gerações,
    podemos continuar; caso contrário, paramos.
    """
    # Aqui você pode adicionar uma condição mais sofisticada, como:
    # - número máximo de gerações
    # - score acima de um limiar
    # - estagnação por várias gerações
    if state.get("replaced", False) and state["best_score"] < 95.0:  # ex: 95 é o alvo
        return "mutate"   # continua tentando
    else:
        return END

# =============================================================================
# 4. CONSTRUÇÃO DO GRAFO
# =============================================================================
def create_atena_graph(core: AtenaCore) -> StateGraph:
    """
    Cria o grafo LangGraph que orquestra o ciclo de evolução.
    """
    # Inicializa o grafo com o estado definido
    graph = StateGraph(AtenaState)

    # Adiciona nós (cada nó recebe o core como argumento via closure)
    graph.add_node("think", lambda state: think_node(state, core))
    graph.add_node("mutate", lambda state: mutate_node(state, core))
    graph.add_node("test", lambda state: test_node(state, core))

    # Define o ponto de entrada
    graph.set_entry_point("think")

    # Conecta os nós
    graph.add_edge("think", "mutate")
    graph.add_edge("mutate", "test")
    graph.add_conditional_edges("test", should_continue)

    # Compila o grafo (pode ser usado como Runnable)
    return graph.compile()

# =============================================================================
# 5. FUNÇÃO PRINCIPAL (exemplo de uso)
# =============================================================================
if __name__ == "__main__":
    # Cria uma instância do AtenaCore (pode passar um problema opcional)
    core = AtenaCore()

    # Inicializa o estado inicial
    initial_state: AtenaState = {
        "messages": [],
        "generation": 0,
        "current_code": core.current_code,
        "best_code": core.current_code,
        "best_score": core.best_score,
        "problem_name": core.problem.name if core.problem else None,
        "problem_description": core.problem.description if core.problem else None,
        "mutation_history": [],
        "last_mutation": None,
        "last_score": core.best_score,
        "replaced": False,
        "error": None,
    }

    # Cria o grafo
    app = create_atena_graph(core)

    # Executa o grafo (pode ser assíncrono ou síncrono)
    # Aqui usamos .invoke() síncrono
    final_state = app.invoke(initial_state)

    # Exibe o resultado
    logger.info(f"Evolução concluída. Melhor score: {final_state['best_score']:.2f}")
    logger.info(f"Código final:\n{final_state['best_code']}")
