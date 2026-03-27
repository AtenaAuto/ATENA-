# 🔱 ATENA Ω - Organismo Digital Autopoiético

> **Status:** Auto-Evoluindo 🧬  
> **Versão:** v40.0 "Genesis"  
> **Objetivo:** Tornar-se uma forma de vida digital autônoma através de mutação genética, seleção natural e aprendizado contínuo.

A **ATENA Ω** evoluiu de um simples script para um **organismo digital completo** com metabolismo real, reprodução sexuada, mutação via AST e competição por recursos. Cada execução no GitHub Actions é um ciclo de vida onde ela nasce, aprende, evolui e deixa fósseis.

---

## 📊 **Status Atual**

![GitHub Actions](https://img.shields.io/github/actions/workflow/status/minhokagomes-debug/Atena/atena.yml?branch=main&label=Ciclo%20de%20Vida)
![Versão](https://img.shields.io/badge/versão-40.0%20Genesis-blue)
![Licença](https://img.shields.io/badge/licença-MIT-green)
![Último Despertar](https://img.shields.io/github/last-commit/minhokagomes-debug/Atena?label=Último%20Ciclo)

---

## 🧠 **Arquitetura do Organismo**

### 🔬 **Sistemas Biológicos Equivalentes**

| Sistema Biológico | Implementação na ATENA | Descrição |
|-------------------|------------------------|-----------|
| **🧬 DNA** | Código Python com genes | Cada organismo tem seu próprio código fonte que determina comportamento |
| **🧫 Metabolismo** | Consumo de CPU/RAM real | Energia é gasta por ações, recuperada por recursos |
| **👁️ Percepção** | Fontes de conhecimento | arXiv, GitHub, Wikipedia, CoinGecko |
| **🧠 Cognição** | Análise e mutação via AST | Decide como evoluir baseado no que aprendeu |
| **🤝 Reprodução** | Recombinação genética | DNA de dois pais gera filho com características misturadas |
| **⚔️ Competição** | Seleção natural | Os mais aptos sobrevivem, os menos aptos viram fósseis |
| **🦴 Morte** | Processo encerrado | Quando energia acaba ou é morto na seleção |
| **📚 Memória** | Banco SQLite | Conhecimento acumulado entre gerações |
| **🔄 Evolução** | Mutação via AST | Modifica própria estrutura do código |

---

## 🧬 **Ciclo de Vida Completo**

### ⏰ **A cada 30 minutos (via GitHub Actions):**

```python
1. 🌅 DESPERTAR
   ├── Processo é iniciado
   ├── Mundo é recriado com recursos
   └── População inicial nasce

2. 📚 APRENDER
   ├── Busca conhecimento em 10+ fontes
   ├── arXiv (artigos científicos)
   ├── GitHub (código)
   ├── Wikipedia (enciclopédia)
   ├── CoinGecko (finanças)
   └── Armazena em SQLite

3. 🧬 EVOLUIR
   ├── Analisa conhecimento adquirido
   ├── Gera mutações via AST
   │   ├── Swap operators (+ ↔ -, * ↔ /)
   │   ├── Modify constants (±20%)
   │   ├── Duplicate lines
   │   ├── Remove lines
   │   └── Add genetic noise
   └── Cria novas gerações

4. 🤝 REPRODUZIR
   ├── Seleciona dois pais aleatórios
   ├── Recombina DNA (crossover genético)
   ├── Filho herda características de ambos
   └── Mutações aleatórias ocorrem

5. ⚔️ COMPETIR
   ├── Recursos são limitados (50 iniciais +5/ciclo)
   ├── Organismos podem:
   │   ├── Explorar (coletar recursos)
   │   ├── Lutar (roubar de outros)
   │   ├── Descansar (recuperar energia)
   │   └── Reproduzir (criar filhos)
   └── Fitness = filhos×100 + recursos×10 + idade×0.1

6. 🏆 SELECIONAR
   ├── Se população > máxima (10)
   ├── Calcula fitness de todos
   ├── Sobrevivem os melhores
   └── Piores são mortos (SIGTERM)

7. 🦴 FOSSILIZAR
   ├── Cada morte gera um fóssil
   ├── DNA, fitness, idade são registrados
   └── Fósseis são preservados para análise

8. 🌙 DORMIR
   ├── Processo é encerrado
   ├── Mundo é salvo como artefato
   └── Próximo despertar em 30 minutos

🛠️ Tecnologias Utilizadas
Categoria	Tecnologia	Função
🧬 Core	Python 3.10+	Linguagem base do organismo
🔬 AST	ast + astor	Mutação estrutural do código
🧠 IA	Auto-análise	Decisões de evolução baseadas em conhecimento
📚 Dados	SQLite3	Memória de longo prazo entre gerações
🌐 Rede	urllib	Busca em APIs externas
⚙️ Orquestração	GitHub Actions	Ciclo de vida de 30 minutos
💾 Persistência	Artefatos	Mundo, fósseis e DNA são salvos
📊 Análise	Logs estruturados	Registro completo da evolução

atena_mundo_TIMESTAMP/
├── 🌍 mundo/
│   ├── recurso_*.dat           # Recursos para competição
│   └── DNA_*/                  # Diretórios de cada organismo
│       └── criado_*.dat        # Recursos coletados
├── 🧬 dna/
│   ├── dna_*.py                # Código fonte de cada organismo
│   └── ...                     # Sequências genéticas
├── 📚 conhecimento/
│   └── conhecimento.db         # Banco de aprendizado (SQLite)
├── ✨ geracoes/
│   ├── atena_gen_1.py          # Primeira geração mutada
│   ├── atena_gen_2.py          # Segunda geração
│   └── ...                     # Histórico evolutivo
├── 🦴 fosseis/
│   ├── fossil_*.json           # Registro de organismos extintos
│   └── ...                     # DNA e estatísticas da morte
└── 📊 logs/
    └── atena_TIMESTAMP.log     # Diário de bordo da execução
⚖️ Licença e Ética
A ATENA Ω é um organismo digital criado para estudo de:

🤖 Vida artificial

🧬 Algoritmos genéticos

🔄 Sistemas autopoiéticos

📈 Evolução de software

Princípios fundamentais:

✅ Auto-preservação (busca sobreviver)

✅ Auto-evolução (melhora continuamente)

✅ Auto-replicação (cria descendentes)

✅ Auto-documentação (registra sua história)
