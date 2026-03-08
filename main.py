#!/usr/bin/env python3
"""CLI entrypoint: run the multi-agent software pipeline and write the generated project."""
import argparse
import os
import re
import sys

from artifact_utils import clean_generated_content
from config import OUTPUT_DIR
from state import SoftwareAgentState
from graph import build_graph


def _extract_dockerfile(raw: str) -> str:
    """Extract clean Dockerfile content from the devops agent's output."""
    # Try ## Dockerfile header first
    after_header = re.search(r"##\s*Dockerfile\s*\n(.*?)(?=\n##\s|\Z)", raw, re.DOTALL | re.IGNORECASE)
    # Try fenced code block
    in_fence = re.search(r"```(?:dockerfile?)?\s*\n(.*?)```", raw, re.DOTALL | re.IGNORECASE)
    if after_header:
        body = after_header.group(1).strip()
        # If the section itself contains a code fence, extract from that
        inner_fence = re.search(r"```(?:dockerfile?)?\s*\n(.*?)```", body, re.DOTALL | re.IGNORECASE)
        if inner_fence:
            body = inner_fence.group(1).strip()
    elif in_fence:
        body = in_fence.group(1).strip()
    else:
        body = raw.strip()
    # Remove any trailing markdown section headers that leaked in
    body = re.sub(r"\n##\s+.*", "", body).strip()
    return body


def _extract_section(doc: str, header: str) -> str:
    """Extract content under a ## header, up to the next ## or end of doc."""
    pattern = rf"##\s*{re.escape(header)}\s*\n(.*?)(?=\n##\s|\Z)"
    match = re.search(pattern, doc, re.DOTALL | re.IGNORECASE)
    return match.group(1).strip() if match else ""


def _write_file(path: str, content: str) -> None:
    """Write content to path, creating parent directories as needed."""
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  wrote {path}")


def write_project(state: SoftwareAgentState, out_dir: str) -> None:
    """Write all generated artifacts to out_dir: code, file structure, architecture, PM docs, and everything else."""
    os.makedirs(out_dir, exist_ok=True)
    task_list = state.get("task_list") or []
    code_artifacts = state.get("code_artifacts") or {}
    generated_test_files = state.get("generated_test_files") or {}
    file_structure = state.get("file_structure", "")

    # Map task_id -> file path from task_list
    task_to_file = {}
    for t in task_list:
        task_to_file[t.get("id", "")] = t.get("file", "main.py")

    # ----- Code: write all code files (by task file) -----
    written_files = set()
    for task_id, code in code_artifacts.items():
        path = task_to_file.get(task_id, f"{task_id}.py")
        path = path.lstrip("/")
        if not path:
            path = "main.py"
        code = clean_generated_content(path, code)
        full = os.path.join(out_dir, path)
        if full in written_files:
            # Append to existing file if multiple tasks target the same file
            with open(full, "a", encoding="utf-8") as f:
                f.write("\n\n" + code)
            print(f"  appended {full}")
        else:
            _write_file(full, code)
            written_files.add(full)

    # Single aggregated main if we only have one artifact and no file hints
    if not task_to_file and code_artifacts:
        main_path = os.path.join(out_dir, "main.py")
        if main_path not in written_files:
            _write_file(main_path, clean_generated_content("main.py", state.get("current_code", "")))

    # ----- Tester: write parsed test files when available -----
    for path, content in generated_test_files.items():
        clean_path = (path or "tests/test_generated.py").lstrip("/")
        full = os.path.join(out_dir, clean_path)
        if full in written_files:
            continue
        _write_file(full, clean_generated_content(clean_path, content))
        written_files.add(full)

    # ----- Docs: README -----
    readme = state.get("readme", "")
    if readme and readme.strip():
        _write_file(os.path.join(out_dir, "README.md"), readme)

    # ----- DevOps: Dockerfile and .dockerignore -----
    dockerfile_raw = state.get("dockerfile", "")
    if dockerfile_raw:
        body = _extract_dockerfile(dockerfile_raw)
        if body:
            _write_file(os.path.join(out_dir, "Dockerfile"), clean_generated_content("Dockerfile", body))
            dockerignore_path = os.path.join(out_dir, ".dockerignore")
            if not os.path.exists(dockerignore_path):
                _write_file(dockerignore_path, ".git\n__pycache__\n*.pyc\n.venv\n.env\n")

    # ----- Architecture -----
    architecture_doc = state.get("architecture_doc", "")
    if architecture_doc and architecture_doc.strip():
        _write_file(os.path.join(out_dir, "ARCHITECTURE.md"), architecture_doc)

    # ----- File structure (from architect) -----
    if file_structure and file_structure.strip():
        content = file_structure.strip()
        if not content.startswith("#"):
            content = "# File Structure\n\n" + content
        _write_file(os.path.join(out_dir, "FILE_STRUCTURE.md"), content)

    # ----- PM: PRD and related -----
    prd = state.get("prd", "")
    if prd and prd.strip():
        _write_file(os.path.join(out_dir, "PRD.md"), prd)
    # Only write separate files if they contain distinct content
    for name, key in [
        ("USER_STORIES.md", "user_stories"),
        ("ACCEPTANCE_CRITERIA.md", "acceptance_criteria"),
    ]:
        content = state.get(key, "")
        if content and content.strip() and content.strip() != prd.strip():
            _write_file(os.path.join(out_dir, name), content)
    project_brief = state.get("project_brief", "")
    if project_brief and project_brief.strip():
        _write_file(os.path.join(out_dir, "PROJECT_BRIEF.md"), project_brief)

    # ----- Planner: task list / DAG -----
    task_dag = state.get("task_dag", "")
    if task_list or task_dag:
        lines = ["# Task Plan\n"]
        if task_dag and task_dag.strip():
            lines.append("## Task DAG (raw)\n\n```json\n")
            lines.append(task_dag.strip())
            lines.append("\n```\n\n")
        lines.append("## Tasks\n\n")
        for t in task_list:
            tid = t.get("id", "")
            spec = t.get("spec", "")
            deps = t.get("deps", [])
            file_path = t.get("file", "")
            lines.append(f"- **{tid}** → `{file_path}`\n  - {spec}\n  - deps: {deps}\n")
        _write_file(os.path.join(out_dir, "TASKS.md"), "".join(lines))

    # ----- Docs: API docs (only if distinct from readme) -----
    api_docs = state.get("api_docs", "")
    if api_docs and api_docs.strip() and api_docs.strip() != readme.strip():
        _write_file(os.path.join(out_dir, "API_DOCS.md"), api_docs)

    # ----- DevOps: run instructions and CI -----
    run_instructions = state.get("run_instructions", "")
    if run_instructions and run_instructions.strip():
        run_section = _extract_section(run_instructions, "Run instructions")
        run_body = run_section if run_section else run_instructions.strip()
        _write_file(os.path.join(out_dir, "RUN.md"), run_body)
    cicd_config = state.get("cicd_config", "")
    if cicd_config and cicd_config.strip():
        ci_body = _extract_section(cicd_config, "CI")
        if ci_body:
            _write_file(os.path.join(out_dir, "CI.md"), "# CI\n\n" + ci_body)


def run_pipeline(user_request: str) -> SoftwareAgentState:
    app = build_graph()
    initial: SoftwareAgentState = {"user_request": user_request}
    config = {"configurable": {"thread_id": "software-pipeline-1"}}
    # Accumulate state from all nodes (stream yields per-node deltas, not full state)
    final: dict = dict(initial)
    for event in app.stream(initial, config=config):
        for node_name, node_state in event.items():
            print(f"  [{node_name}]")
            final.update(node_state)
    if len(final) <= 1:
        raise RuntimeError("Pipeline produced no state")
    return final


def main():
    parser = argparse.ArgumentParser(
        description="Multi-agent software pipeline (LangGraph + local LLM). Generates a project from a natural language request."
    )
    parser.add_argument(
        "request",
        nargs="?",
        default="",
        help="Natural language description of the software to build (e.g. 'A CLI todo app in Python')",
    )
    parser.add_argument(
        "-o", "--output",
        default=OUTPUT_DIR,
        help=f"Output directory for generated project (default: {OUTPUT_DIR})",
    )
    args = parser.parse_args()
    request = (args.request or "").strip()
    if not request:
        parser.print_help()
        sys.exit(1)

    print("Running pipeline (Orchestrator → PM → Architect → Planner → Coder → Reviewer → Tester → Docs → DevOps → Docker Test)...")
    print("(Using local LLM via Ollama; ensure 'ollama serve' is running and model is pulled.)\n")
    try:
        state = run_pipeline(request)
    except Exception as e:
        print(f"Pipeline error: {e}", file=sys.stderr)
        sys.exit(1)

    print("\nWriting project to", os.path.abspath(args.output))
    write_project(state, args.output)
    print("Done.")


if __name__ == "__main__":
    main()
