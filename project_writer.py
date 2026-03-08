"""Shared project/state writing utilities used by the CLI and graph nodes."""
from __future__ import annotations

import json
import os
import re

from artifact_utils import clean_generated_content
from state import SoftwareAgentState


def _extract_dockerfile(raw: str) -> str:
    """Extract clean Dockerfile content from the devops agent's output."""
    after_header = re.search(r"##\s*Dockerfile\s*\n(.*?)(?=\n##\s|\Z)", raw, re.DOTALL | re.IGNORECASE)
    in_fence = re.search(r"```(?:dockerfile?)?\s*\n(.*?)```", raw, re.DOTALL | re.IGNORECASE)
    if after_header:
        body = after_header.group(1).strip()
        inner_fence = re.search(r"```(?:dockerfile?)?\s*\n(.*?)```", body, re.DOTALL | re.IGNORECASE)
        if inner_fence:
            body = inner_fence.group(1).strip()
    elif in_fence:
        body = in_fence.group(1).strip()
    else:
        body = raw.strip()
    return re.sub(r"\n##\s+.*", "", body).strip()


def _extract_section(doc: str, header: str) -> str:
    pattern = rf"##\s*{re.escape(header)}\s*\n(.*?)(?=\n##\s|\Z)"
    match = re.search(pattern, doc, re.DOTALL | re.IGNORECASE)
    return match.group(1).strip() if match else ""


def _write_file(path: str, content: str) -> None:
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  wrote {path}")


def write_project(state: SoftwareAgentState, out_dir: str) -> None:
    """Write the generated project to disk."""
    os.makedirs(out_dir, exist_ok=True)
    task_list = state.get("task_list") or []
    code_artifacts = state.get("code_artifacts") or {}
    generated_test_files = state.get("generated_test_files") or {}
    file_structure = state.get("file_structure", "")
    task_to_file = {t.get("id", ""): t.get("file", "main.py") for t in task_list}

    written_files: set[str] = set()
    for task_id, code in code_artifacts.items():
        path = (task_to_file.get(task_id, f"{task_id}.py") or "main.py").lstrip("/")
        full = os.path.join(out_dir, path)
        content = clean_generated_content(path, code)
        if full in written_files:
            with open(full, "a", encoding="utf-8") as f:
                f.write("\n\n" + content)
            print(f"  appended {full}")
        else:
            _write_file(full, content)
            written_files.add(full)

    if not task_to_file and code_artifacts:
        main_path = os.path.join(out_dir, "main.py")
        if main_path not in written_files:
            _write_file(main_path, clean_generated_content("main.py", state.get("current_code", "")))

    for path, content in generated_test_files.items():
        clean_path = (path or "tests/test_generated.py").lstrip("/")
        full = os.path.join(out_dir, clean_path)
        if full not in written_files:
            _write_file(full, clean_generated_content(clean_path, content))
            written_files.add(full)

    readme = state.get("readme", "")
    if readme and readme.strip():
        _write_file(os.path.join(out_dir, "README.md"), readme)

    dockerfile_raw = state.get("dockerfile", "")
    if dockerfile_raw:
        body = _extract_dockerfile(dockerfile_raw)
        if body:
            _write_file(os.path.join(out_dir, "Dockerfile"), clean_generated_content("Dockerfile", body))
            dockerignore_path = os.path.join(out_dir, ".dockerignore")
            if not os.path.exists(dockerignore_path):
                _write_file(dockerignore_path, ".git\n__pycache__\n*.pyc\n.venv\n.env\n")

    architecture_doc = state.get("architecture_doc", "")
    if architecture_doc and architecture_doc.strip():
        _write_file(os.path.join(out_dir, "ARCHITECTURE.md"), architecture_doc)

    if file_structure and file_structure.strip():
        content = file_structure.strip()
        if not content.startswith("#"):
            content = "# File Structure\n\n" + content
        _write_file(os.path.join(out_dir, "FILE_STRUCTURE.md"), content)

    prd = state.get("prd", "")
    if prd and prd.strip():
        _write_file(os.path.join(out_dir, "PRD.md"), prd)
    for name, key in [("USER_STORIES.md", "user_stories"), ("ACCEPTANCE_CRITERIA.md", "acceptance_criteria")]:
        content = state.get(key, "")
        if content and content.strip() and content.strip() != prd.strip():
            _write_file(os.path.join(out_dir, name), content)
    project_brief = state.get("project_brief", "")
    if project_brief and project_brief.strip():
        _write_file(os.path.join(out_dir, "PROJECT_BRIEF.md"), project_brief)

    task_dag = state.get("task_dag", "")
    if task_list or task_dag:
        lines = ["# Task Plan\n"]
        if task_dag and task_dag.strip():
            lines.append("## Task DAG (raw)\n\n```json\n")
            lines.append(task_dag.strip())
            lines.append("\n```\n\n")
        lines.append("## Tasks\n\n")
        for task in task_list:
            lines.append(
                f"- **{task.get('id', '')}** -> `{task.get('file', '')}`\n"
                f"  - {task.get('spec', '')}\n"
                f"  - deps: {task.get('deps', [])}\n"
            )
        _write_file(os.path.join(out_dir, "TASKS.md"), "".join(lines))

    api_docs = state.get("api_docs", "")
    if api_docs and api_docs.strip() and api_docs.strip() != readme.strip():
        _write_file(os.path.join(out_dir, "API_DOCS.md"), api_docs)

    run_instructions = state.get("run_instructions", "")
    if run_instructions and run_instructions.strip():
        run_section = _extract_section(run_instructions, "Run instructions")
        _write_file(os.path.join(out_dir, "RUN.md"), run_section if run_section else run_instructions.strip())
    cicd_config = state.get("cicd_config", "")
    if cicd_config and cicd_config.strip():
        ci_body = _extract_section(cicd_config, "CI")
        if ci_body:
            _write_file(os.path.join(out_dir, "CI.md"), "# CI\n\n" + ci_body)


def write_state_snapshot(state: SoftwareAgentState, out_dir: str) -> str:
    """Persist the current pipeline state to disk."""
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "AGENT_STATE.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=True, indent=2, default=str)
    print(f"  wrote {path}")
    return path
