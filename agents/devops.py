"""DevOps Agent: Dockerfile, CI stub, run instructions."""
from langchain_core.messages import SystemMessage, HumanMessage

from state import SoftwareAgentState
from llm import get_llm


def devops_node(state: SoftwareAgentState) -> SoftwareAgentState:
    llm = get_llm()
    tech_stack = state.get("tech_stack", "")
    file_structure = state.get("file_structure", "")
    readme = state.get("readme", "")

    system = """You are a DevOps engineer. Given the tech stack and project layout:
1. If the project is Python: produce a minimal Dockerfile that runs the main application (assume main entry in src/ or root).
2. Add a one-line or minimal CI suggestion (e.g. "Run: pytest" or "Use GitHub Actions with pytest").
3. Short "Run instructions": exact commands to run locally and optionally in Docker.

Output format:

## Dockerfile
...
(contents of Dockerfile)

## CI
...

## Run instructions
..."""

    messages = [
        SystemMessage(content=system),
        HumanMessage(content=f"Tech stack:\n{tech_stack}\n\nFile structure:\n{file_structure}\n\nREADME (for context):\n{readme}\n\nProduce Dockerfile, CI, and run instructions."),
    ]
    response = llm.invoke(messages)
    content = response.content if hasattr(response, "content") else str(response)

    return {
        "dockerfile": content,
        "cicd_config": content,
        "run_instructions": content,
        "done": True,
    }
