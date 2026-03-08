# Multi-Agent Software Engineering (LangGraph + Local LLM)

A LangGraph project that implements the multi-agent software architecture from the reference diagram: **Orchestrator → Product Manager → Architect → Planner → Coder → Reviewer → Tester** (with **Debugger** loop) → **Documentation** → **DevOps**. All agents use **local LLMs via Ollama**.

## Architecture

- **Orchestrator**: Parses user requirements, delegates to specialists, manages flow.
- **Product Manager**: Produces PRD, user stories, acceptance criteria.
- **Architect**: System design, tech stack, APIs, high-level structure.
- **Planner**: Breaks work into atomic tasks with dependencies.
- **Coder**: Writes code per task (optionally RAG-augmented).
- **Reviewer**: Code review; can send back to Coder or approve.
- **Tester**: Generates and runs tests; failures go to Debugger.
- **Debugger**: Root cause and patches; sends back to Coder.
- **Documentation**: README, API docs, inline comments.
- **DevOps**: Build/deploy config (e.g. Dockerfile, CI stub).

## Prerequisites

- Python 3.10+
- [Ollama](https://ollama.ai) installed and running (`ollama serve`)
- A pulled model, e.g. `ollama pull llama3` or `ollama pull llama3.2`

## Setup

```bash
cd AgentGraph
python -m venv .venv
source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
```

## Run

```bash
# Default: uses llama3 and writes to ./generated_project
python main.py "A CLI todo app in Python with add/list/complete"

# Custom model and output dir
SOFTWARE_AGENT_MODEL=llama3.1 python main.py "A REST API for book inventory"
SOFTWARE_OUTPUT_DIR=./my_app python main.py "Describe your app here"
```

## Environment

| Variable | Default | Description |
|----------|---------|-------------|
| `OLLAMA_BASE_URL` | `http://127.0.0.1:11434` | Ollama server URL |
| `SOFTWARE_AGENT_MODEL` | `llama3` | Model name for all agents |
| `SOFTWARE_OUTPUT_DIR` | `./generated_project` | Where to write generated project |

## Project layout

```
AgentGraph/
├── config.py           # Config and env
├── state.py            # LangGraph state schema
├── llm.py              # Ollama LLM factory
├── agents/             # Agent node logic
│   ├── __init__.py
│   ├── orchestrator.py
│   ├── pm.py
│   ├── architect.py
│   ├── planner.py
│   ├── coder.py
│   ├── reviewer.py
│   ├── tester.py
│   ├── debugger.py
│   ├── docs.py
│   └── devops.py
├── graph.py            # Build and compile StateGraph
├── main.py             # CLI entrypoint
├── requirements.txt
└── README.md
```
