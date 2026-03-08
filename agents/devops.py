"""DevOps Agent: produces a runnable Dockerfile and run instructions."""
from __future__ import annotations

import os
import re

from artifact_utils import clean_generated_content
from llm import get_llm, get_state_model
from state import SoftwareAgentState
from langchain_core.messages import HumanMessage, SystemMessage


def _task_files(task_list: list[dict]) -> list[str]:
    return [str(task.get("file", "")).strip() for task in task_list if str(task.get("file", "")).strip()]


def _infer_entry_file(task_list: list[dict], code_artifacts: dict[str, str]) -> str:
    """Pick the most likely runnable Python entrypoint."""
    task_files = _task_files(task_list)
    file_to_task_id = {
        str(task.get("file", "")).strip(): str(task.get("id", "")).strip()
        for task in task_list
        if str(task.get("file", "")).strip()
    }
    candidates = [path for path in task_files if path.endswith(".py") and "test" not in path.lower()]
    preferred_patterns = (
        "main.py",
        "app.py",
        "__main__.py",
        "cli.py",
        "server.py",
        "run.py",
    )
    for pattern in preferred_patterns:
        for path in candidates:
            if path.endswith(pattern):
                return path

    for path in candidates:
        code = code_artifacts.get(file_to_task_id.get(path, path), "")
        if "if __name__ == \"__main__\":" in code or "if __name__ == '__main__':" in code:
            return path

    return candidates[0] if candidates else "main.py"


def _infer_dependency_file(task_files: list[str]) -> str:
    for name in ("requirements.txt", "pyproject.toml", "Pipfile"):
        for path in task_files:
            if os.path.basename(path) == name:
                return path
    return "requirements.txt"


def _looks_like_server(project_text: str) -> bool:
    lowered = project_text.lower()
    return any(token in lowered for token in ("api", "server", "http", "fastapi", "flask", "web"))


def _infer_exposed_port(project_text: str) -> int | None:
    match = re.search(r"\b(3000|5000|8000|8080)\b", project_text)
    if match:
        return int(match.group(1))
    if _looks_like_server(project_text):
        return 8000
    return None


def _build_python_dockerfile(
    dependency_file: str,
    entry_file: str,
    project_text: str,
) -> str:
    """Return a deterministic Python Dockerfile."""
    lines = [
        "FROM python:3.11-slim",
        "",
        "ENV PYTHONDONTWRITEBYTECODE=1",
        "ENV PYTHONUNBUFFERED=1",
        "ENV PIP_NO_CACHE_DIR=1",
        "ENV PYTHONPATH=/app",
        "",
        "WORKDIR /app",
        "",
        "COPY . /app",
        "",
        "RUN python -m pip install --upgrade pip",
        "",
    ]

    if os.path.basename(dependency_file) == "requirements.txt":
        lines.append(f"RUN if [ -f {dependency_file} ]; then pip install -r {dependency_file}; fi")
    elif os.path.basename(dependency_file) == "pyproject.toml":
        lines.append("RUN if [ -f pyproject.toml ]; then pip install .; fi")
    elif os.path.basename(dependency_file) == "Pipfile":
        lines.append("RUN if [ -f Pipfile ]; then pip install pipenv && pipenv install --system --deploy; fi")
    lines.extend([
        "",
        "RUN pip install pytest",
        "RUN python -m pytest -v",
    ])

    port = _infer_exposed_port(project_text)
    if port:
        lines.extend(["", f"EXPOSE {port}"])

    cmd = f'CMD ["python", "{entry_file}"]'
    lines.extend(["", cmd])
    return "\n".join(lines).strip()


def _build_python_run_instructions(dependency_file: str, entry_file: str) -> str:
    install_cmd = "python -m pip install --upgrade pip"
    if os.path.basename(dependency_file) == "requirements.txt":
        install_cmd += f" && pip install -r {dependency_file}"
    elif os.path.basename(dependency_file) == "pyproject.toml":
        install_cmd += " && pip install ."
    elif os.path.basename(dependency_file) == "Pipfile":
        install_cmd += " && pip install pipenv && pipenv install --dev"

    return "\n".join(
        [
            "## Run instructions",
            f"Local: {install_cmd} && python {entry_file}",
            "Docker build (runs tests): docker build -t app .",
            "Docker run: docker run --rm app",
            "Docker tests: docker run --rm --entrypoint python app -m pytest -v",
        ]
    )


def _llm_ci_hint(tech_stack: str, readme: str, file_structure: str, model_name: str | None = None) -> str:
    """Use the model only for a short CI suggestion, not the Dockerfile itself."""
    llm = get_llm(model=model_name)
    system = """You are a DevOps engineer. Produce one concise CI command suggestion.

Output only the command or one short sentence, with no markdown fence."""
    human = (
        f"Tech stack:\n{tech_stack}\n\n"
        f"File structure:\n{file_structure}\n\n"
        f"README:\n{readme[:1200]}\n\n"
        "Return a minimal CI command suggestion."
    )
    response = llm.invoke([SystemMessage(content=system), HumanMessage(content=human)])
    content = response.content if hasattr(response, "content") else str(response)
    return clean_generated_content("CI.md", content).strip() or "Run: python -m pytest -v"


def devops_node(state: SoftwareAgentState) -> SoftwareAgentState:
    task_list = state.get("task_list") or []
    task_files = _task_files(task_list)
    code_artifacts = state.get("code_artifacts") or {}
    tech_stack = state.get("tech_stack", "")
    file_structure = state.get("file_structure", "")
    readme = state.get("readme", "")
    architecture_doc = state.get("architecture_doc", "")
    project_text = "\n".join([tech_stack, file_structure, readme[:1200], architecture_doc[:1200]])

    is_python = "python" in tech_stack.lower() or any(path.endswith(".py") for path in task_files)
    dependency_file = _infer_dependency_file(task_files)
    entry_file = _infer_entry_file(task_list, code_artifacts)

    if is_python:
        dockerfile = _build_python_dockerfile(dependency_file, entry_file, project_text)
        run_instructions = _build_python_run_instructions(dependency_file, entry_file)
        ci_section = "Run: python -m pytest -v"
        try:
            ci_section = _llm_ci_hint(tech_stack, readme, file_structure, get_state_model(state)) or ci_section
        except Exception:
            pass
    else:
        dockerfile = (
            "FROM ubuntu:22.04\n\n"
            "WORKDIR /app\n\n"
            "COPY . /app\n\n"
            'CMD ["sh", "-lc", "echo Unsupported tech stack for deterministic Docker generation; inspect project files."]'
        )
        run_instructions = "\n".join(
            [
                "## Run instructions",
                "Local: inspect the generated project and run it with the appropriate toolchain.",
                "Docker build: docker build -t app .",
                "Docker run: docker run --rm app",
            ]
        )
        ci_section = "Inspect the generated project and run its test command."

    return {
        "dockerfile": dockerfile,
        "cicd_config": ci_section,
        "run_instructions": run_instructions,
        "done": True,
    }
