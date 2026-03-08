#!/usr/bin/env python3
"""CLI entrypoint: run the multi-agent software pipeline and write the generated project."""
import argparse
import os
import re
import sys

from config import OUTPUT_DIR
from state import SoftwareAgentState
from graph import build_graph


def write_project(state: SoftwareAgentState, out_dir: str) -> None:
    """Write generated artifacts to out_dir."""
    os.makedirs(out_dir, exist_ok=True)
    task_list = state.get("task_list") or []
    code_artifacts = state.get("code_artifacts") or {}
    file_structure = state.get("file_structure", "")

    # Map task_id -> file path from task_list
    task_to_file = {}
    for t in task_list:
        task_to_file[t.get("id", "")] = t.get("file", "main.py")

    # Write code files (by task file)
    for task_id, code in code_artifacts.items():
        path = task_to_file.get(task_id, f"{task_id}.py")
        path = path.lstrip("/")
        if not path:
            path = "main.py"
        full = os.path.join(out_dir, path)
        d = os.path.dirname(full)
        if d:
            os.makedirs(d, exist_ok=True)
        with open(full, "w", encoding="utf-8") as f:
            f.write(code)
        print(f"  wrote {full}")

    # Single aggregated main if we only have one artifact and no file hints
    if not task_to_file and code_artifacts:
        main_path = os.path.join(out_dir, "main.py")
        with open(main_path, "w", encoding="utf-8") as f:
            f.write(state.get("current_code", ""))
        print(f"  wrote {main_path}")

    # README
    readme = state.get("readme", "")
    if readme:
        readme_path = os.path.join(out_dir, "README.md")
        with open(readme_path, "w", encoding="utf-8") as f:
            f.write(readme)
        print(f"  wrote {readme_path}")

    # Dockerfile (DevOps always produces one for the full package)
    dockerfile_raw = state.get("dockerfile", "")
    if dockerfile_raw:
        # Extract content after "## Dockerfile" or between ```dockerfile ... ```
        after_header = re.search(r"##\s*Dockerfile\s*\n(.*?)(?=\n##\s|\Z)", dockerfile_raw, re.DOTALL | re.IGNORECASE)
        in_fence = re.search(r"```(?:dockerfile?)?\s*\n(.*?)```", dockerfile_raw, re.DOTALL | re.IGNORECASE)
        if after_header:
            body = after_header.group(1).strip()
        elif in_fence:
            body = in_fence.group(1).strip()
        else:
            body = dockerfile_raw.strip()
        # Drop any trailing markdown sections (## CI, ## Run)
        body = re.sub(r"\n##\s+.*", "", body).strip()
        df_path = os.path.join(out_dir, "Dockerfile")
        with open(df_path, "w", encoding="utf-8") as f:
            f.write(body)
        print(f"  wrote {df_path}")
        # .dockerignore to keep image small
        dockerignore_path = os.path.join(out_dir, ".dockerignore")
        if not os.path.exists(dockerignore_path):
            with open(dockerignore_path, "w", encoding="utf-8") as f:
                f.write(".git\n__pycache__\n*.pyc\n.venv\n.env\n*.md\n")
            print(f"  wrote {dockerignore_path}")

    # Optional: architecture and PRD as docs
    for name, content in [
        ("ARCHITECTURE.md", state.get("architecture_doc")),
        ("PRD.md", state.get("prd")),
    ]:
        if content:
            p = os.path.join(out_dir, name)
            with open(p, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"  wrote {p}")


def run_pipeline(user_request: str, out_dir: str) -> SoftwareAgentState:
    app = build_graph()
    initial: SoftwareAgentState = {"user_request": user_request}
    config = {"configurable": {"thread_id": "software-pipeline-1"}}
    final = None
    for event in app.stream(initial, config=config):
        for node_name, node_state in event.items():
            print(f"  [{node_name}]")
            final = node_state
    if final is None:
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

    print("Running pipeline (Orchestrator → PM → Architect → Planner → Coder → Reviewer → Tester → Docs → DevOps)...")
    print("(Using local LLM via Ollama; ensure 'ollama serve' is running and model is pulled.)\n")
    try:
        state = run_pipeline(request, args.output)
    except Exception as e:
        print(f"Pipeline error: {e}", file=sys.stderr)
        sys.exit(1)

    print("\nWriting project to", os.path.abspath(args.output))
    write_project(state, args.output)
    print("Done.")


if __name__ == "__main__":
    main()
