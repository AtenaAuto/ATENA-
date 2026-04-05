# ATENA Ω

ATENA Ω é uma plataforma modular para execução de assistente de terminal, missões autônomas e gates de qualidade para evolução segura do sistema.

## Principais capacidades

- **Assistant interativo** com comandos de contexto, plano e execução local.
- **Missões autônomas** (research, codex, guardian, genius, code-build).
- **Validação de produção** com `doctor`, `guardian` e `production-ready`.
- **Arquitetura modular** com componentes em `core/`, `modules/` e `protocols/`.

## Estrutura do repositório

- `core/` → launcher, assistant, doctor, pipelines e runtime principal.
- `modules/` → módulos funcionais (browser agent, orchestrators, code module, etc.).
- `protocols/` → entrypoints de missões executáveis via CLI.
- `docs/` → relatórios, propostas e registros de execução.
- `atena_evolution/` → artefatos de execução (runtime, relatórios JSON, memória).

## Requisitos

- Python 3.10+
- Dependências em `setup/requirements.txt`

Instalação:

```bash
cd setup
pip install -r requirements.txt
```

## Execução rápida

```bash
./atena help
./atena start
```

## Comandos principais

| Comando | Descrição |
|---|---|
| `./atena assistant` | Assistente de terminal com evolução em background |
| `./atena doctor` | Diagnóstico rápido de ambiente |
| `./atena guardian` | Gate essencial (autopilot + smoke) |
| `./atena production-ready` | Gate final de release (`doctor` + `guardian`) |
| `./atena modules-smoke` | Smoke test dos módulos |
| `./atena codex-advanced` | Missão de diagnóstico estratégico |
| `./atena research-lab` | Gera proposta avançada de evolução |
| `./atena genius` | Planejamento multiobjetivo |
| `./atena code-build --type <site\|api\|cli> --name <projeto> [--template basic\|landing-page\|portfolio\|dashboard\|blog]` | Gera projeto inicial automaticamente |
| `./atena telemetry-report` | Consolida métricas de missão (telemetria) |
| `./atena professional-launch --segment "<segmento>" --pilots <n>` | Gera plano de divulgação e adoção profissional |
| `./atena go-no-go` | Executa checklist de 5 testes para validação pré-divulgação |

## Fluxo recomendado para produção

```bash
./atena doctor
./atena guardian
./atena production-ready
```

Se qualquer etapa falhar, corrigir antes de promover alterações.

### Exemplo de geração de site mais completo

```bash
./atena code-build --type site --name minha_landing --template landing-page
```

### Exemplo de plano de lançamento profissional

```bash
./atena professional-launch --segment "software houses e squads de produto" --pilots 5
```

### Exemplo de varredura Go/No-Go (5 itens)

```bash
./atena go-no-go
```

No modo `assistant`, use `/model list` e `/model set <provider:model>` com providers `local`, `deepseek`, `openai`, `anthropic` e `compat` (OpenAI-compatible).

No terminal assistant (estilo Claude Code), você também pode usar `/tools`, `/review`, `/commit <mensagem>`, `/init-context` e sair com `:q`.

## CI

O repositório inclui workflow de gate em `.github/workflows/production-gate.yml`, executado em `push`/`pull_request` para `main`.


## Análise estratégica

Ver análise e roadmap recomendado em `docs/ANALISE_COMPLETA_ATENA_RECOMENDACOES_2026-04-05.md`.

## Licença

Consulte `LICENSE`.
