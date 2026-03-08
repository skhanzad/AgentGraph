#!/usr/bin/env python3
"""CLI entrypoint: run the multi-agent software pipeline and write the generated project."""
import argparse
import os
import sys

from config import OUTPUT_DIR
from state import SoftwareAgentState
from graph import build_graph


def run_pipeline(user_request: str, out_dir: str) -> SoftwareAgentState:
    app = build_graph()
    initial: SoftwareAgentState = {"user_request": user_request, "output_dir": out_dir}
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

    print("Running pipeline (Orchestrator → [PM || Architect] → Planner → Coder → Project Writer → Git → Reviewer → Tester → [Docs || DevOps] → Project Writer → Git)...")
    print("(Using local LLM via Ollama; ensure 'ollama serve' is running and model is pulled.)\n")
    try:
        state = run_pipeline(request, args.output)
    except Exception as e:
        print(f"Pipeline error: {e}", file=sys.stderr)
        sys.exit(1)

    print("\nProject written to", os.path.abspath(args.output))
    if state.get("git_commit_hash"):
        print("Git commit:", state["git_commit_hash"])
    elif state.get("git_status"):
        print("Git status:", state["git_status"])
    print("Done.")


if __name__ == "__main__":
    main()
