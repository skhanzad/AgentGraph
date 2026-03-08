"""DevOps Agent: produces Dockerfile and run instructions for the full package."""
import re

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

    # Identify test files from the task list
    test_files = [f for f in task_files if "test" in f.lower()]

    system = """You are a DevOps engineer. Your job is to produce a complete Dockerfile so the entire codebase — including tests — runs as a containerized package.

Requirements for the Dockerfile:
- Base image appropriate for the tech stack (e.g. python:3.11-slim for Python).
- Copy the FULL project into the image including test files (COPY . /app or similar).
- Install ALL dependencies including test runners. For Python: RUN pip install --no-cache-dir -r requirements.txt && pip install pytest (always include pytest even if not in requirements.txt).
- Set WORKDIR to the project root inside the container.
- Expose any needed port (EXPOSE if it's a server).
- Set CMD to run the main application (e.g. CMD ["python", "src/main.py"]).
- The image must support running tests by overriding CMD at runtime, e.g. `docker run image python -m pytest -v`.
- No placeholder or "fill in" steps—the Dockerfile must be complete and runnable as-is.

Output format (use these exact section headers):

## Dockerfile
<full Dockerfile content, line by line, no markdown code fence around it>

## CI
One-line or minimal CI suggestion (e.g. "Run: pytest").

## Run instructions
Exact commands: how to run locally (e.g. pip install -r requirements.txt && python src/main.py) and how to build/run with Docker (docker build -t app . && docker run app).
Include how to run tests: docker run app python -m pytest -v"""

    messages = [
        SystemMessage(content=system),
        HumanMessage(
            content=f"Tech stack:\n{tech_stack}\n\nFile structure:\n{file_structure}\n\n"
            f"Dependency file present: {has_requirements}. Main entry hint: {entry_hint}\n"
            f"Test files: {test_files}\n\n"
            f"README (context):\n{readme[:1500]}\n\nProduce a complete Dockerfile plus CI and run instructions."
        ),
    ]
    response = llm.invoke(messages)
    content = response.content if hasattr(response, "content") else str(response)

    # Extract individual sections so downstream consumers get clean data
    def _section(header):
        match = re.search(rf"##\s*{re.escape(header)}\s*\n(.*?)(?=\n##\s|\Z)", content, re.DOTALL | re.IGNORECASE)
        return match.group(1).strip() if match else ""

    dockerfile_section = _section("Dockerfile") or content
    ci_section = _section("CI")
    run_section = _section("Run instructions") or _section("Run")

    return {
        "dockerfile": dockerfile_section,
        "cicd_config": ci_section,
        "run_instructions": run_section or content,
        "done": True,
    }
