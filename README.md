# 🔱 ATENA Ω (Atena-code)

ATENA Ω é uma IA,para execução de assistentes de terminal, missões autônomas e gates de qualidade e evolução segura de sistemas. uma arquitetura de agentes modernos, a Atena combina execução local com capacidades avançadas de orquestração.

---

## 🚀 Início Rápido

### Requisitos
- Python 3.10+
- Acesso à internet para modelos remotos (opcional)

### Instalação. 💻 Windows
```bash
# git clone [https://github.com/AtenaAuto/ATENA-.git](https://github.com/AtenaAuto/ATENA-.git)
cd ATENA-
cd setup
pip install -r requirements.txt
cd ..

```
### Instalação 📱 Android
```bash
pkg update && pkg upgrade -y && pkg install git python clang make -y && git clone [https://github.com/AtenaAuto/ATENA-.git](https://github.com/AtenaAuto/ATENA-.git) && cd ATENA- && cd setup && pip install -r requirements.txt && cd ..

### Execução 
```bash
# Verifique se o ambiente está pronto
./atena doctor

# Inicie o assistente interativo
./atena assistant
```

---

## 🛠️ Comandos Principais

| Comando | Descrição |
| :--- | :--- |
| `./atena assistant` | Assistente de terminal interativo com evolução em background |
| `./atena doctor` | Diagnóstico rápido de ambiente e dependências |
| `./atena guardian` | Gate essencial de segurança (autopilot + smoke tests) |
| `./atena production-ready` | Validação final para release (`doctor` + `guardian`) |
| `./atena code-build` | Gerador automático de projetos (Site, API, CLI) |
| `./atena research-lab` | Gera propostas estratégicas de evolução do sistema |
| `./atena go-no-go` | Checklist de 5 testes para validação pré-divulgação |

---

## 📂 Estrutura do Projeto

- **`core/`**: Núcleo do sistema, incluindo launcher, assistant e runtime principal.
- **`modules/`**: Módulos funcionais (Browser Agent, Codex, Telemetry, etc.).
- **`protocols/`**: Entrypoints para missões autônomas e tarefas específicas.
- **`setup/`**: Scripts de instalação e arquivos de requisitos.
- **`docs/`**: Documentação técnica, relatórios e roadmaps.
- **`atena_evolution/`**: Artefatos de execução, logs e memória persistente.

---

## 🛡️ Fluxo de Qualidade (CI/CD)

Para garantir a estabilidade, utilize o fluxo recomendado antes de qualquer alteração importante:

1. `./atena doctor` (Verifica ambiente)
2. `./atena guardian` (Verifica integridade e riscos)
3. `./atena production-ready` (Validação final)

---

## 📝 Licença

Este projeto está sob a licença definida no arquivo `LICENSE`.

---
*Desenvolvido por AtenaAuto Team*
