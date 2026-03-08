"""Documentation Agent: README, API docs, inline comments."""
import re

from langchain_core.messages import SystemMessage, HumanMessage

from state import SoftwareAgentState
from llm import get_state_llm


def docs_node(state: SoftwareAgentState) -> SoftwareAgentState:
    llm = get_state_llm(state)
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

    # Extract API section separately so it can be written as a standalone doc
    api_match = re.search(r"## API.*?\n(.*?)(?=\n## |\Z)", content, re.DOTALL | re.IGNORECASE)
    api_docs = api_match.group(0).strip() if api_match else ""

    return {
        "readme": content,
        "api_docs": api_docs,
    }
