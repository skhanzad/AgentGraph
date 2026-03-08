"""DevOps Agent: produces Dockerfile and run instructions for the full package."""
from langchain_core.messages import SystemMessage, HumanMessage

from state import SoftwareAgentState
from llm import get_llm


def devops_node(state: SoftwareAgentState) -> SoftwareAgentState:
    llm = get_llm()
    tech_stack = state.get("tech_stack", "")
    file_structure = state.get("file_structure", "")
    readme = state.get("readme", "")
    code_artifacts = state.get("code_artifacts") or {}
    task_list = state.get("task_list") or []

    # Infer entry and dependency file from tasks
    task_files = [t.get("file", "") for t in task_list]
    has_requirements = any("requirements" in f for f in task_files)
    entry_hint = "src/main.py" if any("main" in f for f in task_files) else "main.py"

    system = """You are a DevOps engineer. Your job is to produce a complete Dockerfile so the entire codebase runs as a containerized package.

Requirements for the Dockerfile:
- Base image appropriate for the tech stack (e.g. python:3.11-slim for Python).
- Copy the full project into the image (COPY . . or COPY project/ .).
- Install dependencies: for Python use RUN pip install -r requirements.txt (or pip install . if pyproject.toml exists).
- Set working directory and expose any needed port (EXPOSE if it's a server).
- Set CMD or ENTRYPOINT to run the main application (e.g. CMD ["python", "src/main.py"] or CMD ["python", "-m", "src.main"]).
- No placeholder or "fill in" steps—the Dockerfile must be complete and runnable as-is.

Output format (use these exact section headers):

## Dockerfile
<full Dockerfile content, line by line, no markdown code fence around it>

## CI
One-line or minimal CI suggestion (e.g. "Run: pytest").

## Run instructions
Exact commands: how to run locally (e.g. pip install -r requirements.txt && python src/main.py) and how to build/run with Docker (docker build -t app . && docker run app)."""

    messages = [
        SystemMessage(content=system),
        HumanMessage(
            content=f"Tech stack:\n{tech_stack}\n\nFile structure:\n{file_structure}\n\n"
            f"Dependency file present: {has_requirements}. Main entry hint: {entry_hint}\n\n"
            f"README (context):\n{readme[:1500]}\n\nProduce a complete Dockerfile plus CI and run instructions."
        ),
    ]
    response = llm.invoke(messages)
    content = response.content if hasattr(response, "content") else str(response)

    return {
        "dockerfile": content,
        "cicd_config": content,
        "run_instructions": content,
        "done": True,
    }
