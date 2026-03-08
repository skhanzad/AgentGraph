"""Architect Agent: system design, tech stack, APIs, file structure."""
from langchain_core.messages import SystemMessage, HumanMessage

from state import SoftwareAgentState
from llm import get_llm


def architect_node(state: SoftwareAgentState) -> SoftwareAgentState:
    llm = get_llm()
    project_brief = state.get("project_brief", "")
    prd = state.get("prd", "")

    system = """You are a Software Architect. Given the project brief and PRD, produce:
1. Tech stack: language(s), key libraries/frameworks, and why.
2. High-level architecture: main components and how they interact (1 short paragraph).
3. API design (if applicable): main endpoints or modules and their purpose (bullet list).
4. File/folder structure: proposed directory layout as a tree, e.g.:
   project/
     src/
       main.py
     tests/
     README.md

Output in this exact structure:

## Tech Stack
...

## Architecture
...

## API / Modules
...

## File Structure
...
"""

    messages = [
        SystemMessage(content=system),
        HumanMessage(content=f"Project brief:\n{project_brief}\n\nPRD / User stories:\n{prd}\n\nProduce architecture document."),
    ]
    response = llm.invoke(messages)
    content = response.content if hasattr(response, "content") else str(response)

    return {
        "architecture_doc": content,
        "tech_stack": content,
        "api_design": content,
        "file_structure": content,
    }
