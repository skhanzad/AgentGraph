"""Code Reviewer Agent: quality gate, can reject and send back to Coder."""
from __future__ import annotations

from langchain_core.messages import SystemMessage, HumanMessage

from state import SoftwareAgentState
from llm import get_state_llm
from config import MAX_REVIEW_ITERATIONS
from rag import build_rag_context, store_output


def _render_review_scope(state: SoftwareAgentState) -> str:
    code_artifacts = state.get("code_artifacts") or {}
    task_list = state.get("task_list") or []
    sections: list[str] = []

    for task in task_list:
        task_id = str(task.get("id", "")).strip()
        path = str(task.get("file", "")).strip() or f"{task_id}.txt"
        content = str(code_artifacts.get(task_id, "")).strip()
        if not content:
            continue
        sections.append(f"### {path}\n{content}")

    for path, content in (state.get("generated_test_files") or {}).items():
        clean_path = str(path or "tests/test_generated.py").strip()
        sections.append(f"### {clean_path}\n{str(content).strip()}")

    if not sections:
        current_code = str(state.get("current_code", "")).strip()
        if current_code:
            sections.append(f"### aggregated_code\n{current_code}")

    return "\n\n".join(section for section in sections if section.strip())


def _parse_review_verdict(raw_content: str) -> tuple[bool, str]:
    lines = [line.strip() for line in raw_content.splitlines() if line.strip()]
    verdict = lines[0].upper() if lines else ""
    if verdict.startswith("APPROVED"):
        return True, "APPROVED"
    return False, "REJECTED"


def _find_missing_task_outputs(state: SoftwareAgentState) -> list[str]:
    code_artifacts = state.get("code_artifacts") or {}
    task_list = state.get("task_list") or []
    missing: list[str] = []
    for task in task_list:
        task_id = str(task.get("id", "")).strip()
        file_path = str(task.get("file", "")).strip() or task_id
        if task_id and task_id not in code_artifacts:
            missing.append(file_path)
    return missing


def reviewer_node(state: SoftwareAgentState) -> SoftwareAgentState:
    llm = get_state_llm(state)
    architecture_doc = state.get("architecture_doc", "")
    task_list = state.get("task_list", [])
    review_iteration = state.get("review_iteration", 0)
    review_scope = _render_review_scope(state)
    missing_outputs = _find_missing_task_outputs(state)

    if not review_scope:
        error = "Reviewer received an empty codebase; there is nothing to review."
        return {
            "review_feedback": error,
            "review_passed": False,
            "review_iteration": review_iteration + 1,
            "review_judgement": "FAILED_TO_CONVERGE",
            "error": error,
        }

    if missing_outputs:
        feedback = "REJECTED\n" + "\n".join(f"- missing implementation for `{path}`" for path in missing_outputs)
        return {
            "review_feedback": feedback,
            "review_passed": False,
            "review_iteration": review_iteration + 1,
            "review_judgement": "REJECTED",
        }

    rag_ctx = build_rag_context("reviewer", f"code review {review_scope[:200]}")

    system = """You are a Code Reviewer. Review every file in the supplied codebase for:
1. Correctness and alignment with the architecture.
2. Obvious bugs, security issues, or bad practices.
3. Readability and style.
4. Missing files, incomplete implementations, or contradictions across files.

You must review the full codebase, not a sample.

Output format:
APPROVED
or
REJECTED
- required change
- required change"""

    human = f"Architecture:\n{architecture_doc}\n\nTasks:\n{task_list}\n\nFull codebase to review:\n{review_scope}"
    if rag_ctx:
        human += f"\n\nRetrieved coding standards / past reviews:\n{rag_ctx}"
    human += "\n\nVerdict (APPROVED or REJECTED + feedback):"

    messages = [SystemMessage(content=system), HumanMessage(content=human)]
    response = llm.invoke(messages)
    raw_content = (response.content if hasattr(response, "content") else str(response)).strip()
    passed, judgement = _parse_review_verdict(raw_content)
    feedback = "" if passed else raw_content

    error = None
    if not passed and review_iteration >= MAX_REVIEW_ITERATIONS - 1:
        judgement = "FAILED_TO_CONVERGE"
        error = (
            f"Reviewer did not approve the full codebase after {MAX_REVIEW_ITERATIONS} iterations.\n\n"
            f"Last feedback:\n{feedback or raw_content}"
        )

    store_output("reviewer", feedback or "APPROVED", collection="episodic")

    return {
        "review_feedback": feedback,
        "review_passed": passed,
        "review_iteration": review_iteration + 1,
        "review_judgement": judgement,
        "error": error,
    }
