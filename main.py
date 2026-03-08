#!/usr/bin/env python3
"""CLI entrypoint: run the multi-agent software pipeline and write the generated project."""
import argparse
import os
import sys

from config import OUTPUT_DIR
from memory import MemoryStore
from state import SoftwareAgentState
from graph import build_graph


def run_pipeline(
    user_request: str,
    out_dir: str,
    model_name: str | None = None,
    reset_project_memory: bool = True,
) -> SoftwareAgentState:
    if reset_project_memory:
        MemoryStore.get().reset_project_memory()
    app = build_graph()
    initial: SoftwareAgentState = {
        "user_request": user_request,
        "output_dir": out_dir,
    }
    if model_name:
        initial["model_name"] = model_name
    config = {"configurable": {"thread_id": "software-pipeline-1"}}
    # Accumulate state from all nodes (stream yields per-node deltas, not full state)
    final: dict = dict(initial)
    for event in app.stream(initial, config=config):
        for node_name, node_state in event.items():
            print(f"  [{node_name}]")
            final.update(node_state)
    if len(final) <= 1:
        raise RuntimeError("Pipeline produced no state")
    if final.get("error"):
        raise RuntimeError(str(final["error"]))
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
    parser.add_argument(
        "-m", "--model",
        default="qwen2.5-coder:7b",
        help="Ollama model to use for this run (overrides SOFTWARE_AGENT_MODEL).",
    )
    parser.add_argument(
        "--preserve-project-memory",
        action="store_true",
        help="Keep existing episodic/codebase/architecture memory instead of resetting it before the run.",
    )
    args = parser.parse_args()
    request = (args.request or "").strip()
    if not request:
        parser.print_help()
        sys.exit(1)
    model_name = (args.model or "").strip()

    print("Running pipeline (Orchestrator → [PM || Architect] → Planner → Coder → Debugger → Docs → Project Writer → Git → Reviewer → Tester → [Docs || DevOps] → Project Writer → Git)...")
    if model_name:
        print(f"(Using local LLM via Ollama with model: {model_name})")
    else:
        print("(Using local LLM via Ollama; ensure 'ollama serve' is running and model is pulled.)")
    if args.preserve_project_memory:
        print("(Preserving existing project-scoped memory.)\n")
    else:
        print("(Resetting project-scoped memory before the run; persistent knowledge memory is kept.)\n")
    try:
        state = run_pipeline(
            request,
            args.output,
            model_name=model_name or None,
            reset_project_memory=not args.preserve_project_memory,
        )
    except Exception as e:
        print(f"Pipeline error: {e}", file=sys.stderr)
        sys.exit(1)

    print("\nProject written to", os.path.abspath(args.output))
    if state.get("git_commit_hash"):
        print("Git commit:", state["git_commit_hash"])
    elif state.get("git_status"):
        print("Git status:", state["git_status"])
    if state.get("review_judgement"):
        print("Reviewer verdict:", state["review_judgement"])
    print("Done.")


if __name__ == "__main__":
    main()
