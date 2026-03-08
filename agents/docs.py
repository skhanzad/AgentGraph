"""Documentation Agent: README, API docs, inline comments."""
from langchain_core.messages import SystemMessage, HumanMessage

from state import SoftwareAgentState
from llm import get_llm


def docs_node(state: SoftwareAgentState) -> SoftwareAgentState:
    llm = get_llm()
    prd = state.get("prd", "")
    architecture_doc = state.get("architecture_doc", "")
    current_code = state.get("current_code", "")
    file_structure = state.get("file_structure", "")

    system = """You are a Technical Writer. Produce:
1. README.md content: project name, short description, prerequisites, how to install and run, and basic usage (commands or API summary). No redundant boilerplate.
2. Optional: a short "API / Module overview" section if the project has clear modules or endpoints.

Output in this structure (use the headers):

# <Project Name>

## Description
...

## Prerequisites
...

## Install & Run
...

## Usage
...

## API / Module overview (if applicable)
..."""

    messages = [
        SystemMessage(content=system),
        HumanMessage(content=f"PRD:\n{prd}\n\nArchitecture:\n{architecture_doc}\n\nFile structure:\n{file_structure}\n\nCode:\n{current_code}\n\nProduce README and API overview."),
    ]
    response = llm.invoke(messages)
    content = response.content if hasattr(response, "content") else str(response)

    return {
        "readme": content,
        "api_docs": content,
        "inline_docs": "",
    }
