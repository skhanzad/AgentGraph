"""Architect Agent: produces Architecture.md for the rest of the pipeline."""
from langchain_core.messages import SystemMessage, HumanMessage

from state import SoftwareAgentState
from llm import get_llm


def architect_node(state: SoftwareAgentState) -> SoftwareAgentState:
    llm = get_llm()
    project_brief = state.get("project_brief", "")
    prd = state.get("prd", "")

    system = """You are a Software Architect. Your output will be saved as Architecture.md and used by all downstream agents (Planner, Coder, Reviewer, Tester, Docs, DevOps). Produce a single, self-contained Architecture.md document.

Include these sections (use exactly these headers so other agents can parse them):

# Architecture

## Tech Stack
Language(s), key libraries/frameworks, and brief rationale.

## High-Level Design
Main components and how they interact (one short paragraph).

## API / Modules
If applicable: main endpoints, modules, or public interfaces with their purpose (bullet list). Otherwise describe the main entry points and modules.

## File Structure
Proposed directory layout as a tree. Example:
```
project/
  src/
    main.py
  tests/
  README.md
```

Output only the markdown content of Architecture.md. Start with "# Architecture". No preamble or meta-commentary."""

    messages = [
        SystemMessage(content=system),
        HumanMessage(content=f"Project brief:\n{project_brief}\n\nPRD / User stories:\n{prd}\n\nProduce Architecture.md content."),
    ]
    response = llm.invoke(messages)
    content = response.content if hasattr(response, "content") else str(response)
    content = content.strip()
    if not content.startswith("#"):
        content = "# Architecture\n\n" + content

    return {
        "architecture_doc": content,
        "tech_stack": content,
        "api_design": content,
        "file_structure": content,
    }
