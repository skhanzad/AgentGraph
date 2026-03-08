"""Architect Agent: produces Architecture.md for the rest of the pipeline."""
import re

from langchain_core.messages import SystemMessage, HumanMessage

from state import SoftwareAgentState
from llm import get_llm
from rag import build_rag_context, store_output


def _extract_section(doc: str, header: str) -> str:
    """Extract content under a ## header, up to the next ## or end of doc."""
    pattern = rf"##\s*{re.escape(header)}\s*\n(.*?)(?=\n##\s|\Z)"
    match = re.search(pattern, doc, re.DOTALL | re.IGNORECASE)
    return match.group(1).strip() if match else ""


def architect_node(state: SoftwareAgentState) -> SoftwareAgentState:
    llm = get_llm()
    project_brief = state.get("project_brief", "")
    prd = state.get("prd", "")

    # RAG: retrieve past architecture decisions + web docs for tech stack
    rag_ctx = build_rag_context(
        "architect",
        f"{project_brief[:300]} architecture design",
        web_query=f"{project_brief[:100]} framework architecture best practices",
    )

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
Proposed directory layout as a complete, shippable package. Must include:
- Dependency file: requirements.txt (Python) or equivalent (e.g. package.json, go.mod).
- Source layout: e.g. src/ or a top-level package with main entry point.
- Tests: tests/ or test file(s).
- README.md (Docs agent will fill content).

Example for a Python package:
```
project/
  requirements.txt
  src/
    __init__.py
    main.py
  tests/
    test_main.py
  README.md
```

Output only the markdown content of Architecture.md. Start with "# Architecture". No preamble or meta-commentary."""

    human = f"Project brief:\n{project_brief}\n\nPRD / User stories:\n{prd}"
    if rag_ctx:
        human += f"\n\nRetrieved reference material:\n{rag_ctx}"
    human += "\n\nProduce Architecture.md content."

    messages = [SystemMessage(content=system), HumanMessage(content=human)]
    response = llm.invoke(messages)
    content = response.content if hasattr(response, "content") else str(response)
    content = content.strip()
    if not content.startswith("#"):
        content = "# Architecture\n\n" + content

    # Store architecture in memory for downstream agents
    store_output("architect", content, collection="architecture")

    # Extract individual sections for downstream agents
    tech_stack = _extract_section(content, "Tech Stack")
    api_design = _extract_section(content, "API / Modules") or _extract_section(content, "API")
    file_structure = _extract_section(content, "File Structure")

    return {
        "architecture_doc": content,
        "tech_stack": tech_stack or content,
        "api_design": api_design,
        "file_structure": file_structure,
    }
