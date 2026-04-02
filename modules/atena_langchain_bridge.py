from langgraph.graph import StateGraph, END
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage
from typing import TypedDict, Annotated, Sequence
import operator

# Seu estado atual da ATENA
class AtenaState(TypedDict):
    messages: Annotated[Sequence, operator.add]
    current_problem: dict  # sua classe Problem
    generation: int
    best_score: float
    # ... outros campos do seu atena_state.json

# Ferramentas LangChain que chamam seu MutationEngine / Sandbox
@tool
def mutate_code(code: str, mutation_type: str) -> str:
    """Usa o MutationEngine da ATENA para aplicar mutação AST."""
    # Chame seu MutationEngine aqui
    return "Código mutado com sucesso..."

@tool
def evaluate_in_sandbox(code: str) -> dict:
    """Executa no RecursiveSandbox da ATENA e retorna score."""
    # Integre com sua Sandbox + EvolvableScorer
    return {"score": 0.87, "feedback": "Melhoria detectada em performance"}

# Construa o grafo com LangGraph
def create_atena_graph():
    graph = StateGraph(AtenaState)
    
    # Nodes
    def think_node(state):
        # Use seu local LM (Torch + LoRA) ou Grok via xAI
        # ou um LLM wrapper do LangChain
        return {"messages": [HumanMessage(content="Analisando próxima mutação...")]}
    
    def mutate_node(state):
        # Chama mutate_code tool
        return state
    
    def test_node(state):
        # Chama evaluate_in_sandbox
        return state
    
    # Adicione edges com condições (ex: se score < threshold → mutate novamente)
    graph.add_node("think", think_node)
    graph.add_node("mutate", mutate_node)
    graph.add_node("test", test_node)
    
    graph.set_entry_point("think")
    graph.add_conditional_edges("test", lambda s: "mutate" if s["best_score"] < 0.9 else END)
    
    return graph.compile()
