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
    existing_readme = state.get("readme", "")
    review_judgement = state.get("review_judgement", "")
    phase = "final release polish" if state.get("orchestration_phase") == "release_parallel" else "iterative project draft"

    system = """You are a Technical Writer. Produce or revise a README.md iteratively.
1. README.md content: project name, short description, prerequisites, how to install and run, and basic usage (commands or API summary). No redundant boilerplate.
2. Optional: a short "API / Module overview" section if the project has clear modules or endpoints.
3. If an existing README is provided, improve it instead of starting over from scratch. Keep good sections that are still accurate.

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
        HumanMessage(
            content=(
                f"Mode: {phase}\n\n"
                f"PRD:\n{prd}\n\n"
                f"Architecture:\n{architecture_doc}\n\n"
                f"File structure:\n{file_structure}\n\n"
                f"Code:\n{current_code}\n\n"
                f"Current reviewer judgement:\n{review_judgement}\n\n"
                f"Existing README draft:\n{existing_readme}\n\n"
                "Produce the next README iteration and API overview."
            )
        ),
    ]
    response = llm.invoke(messages)
    content = response.content if hasattr(response, "content") else str(response)

    # Extract API section separately so it can be written as a standalone doc
    api_match = re.search(r"## API.*?\n(.*?)(?=\n## |\Z)", content, re.DOTALL | re.IGNORECASE)
    api_docs = api_match.group(0).strip() if api_match else ""

    return {
        "readme": content,
        "api_docs": api_docs,
        "readme_iteration": state.get("readme_iteration", 0) + 1,
    }
