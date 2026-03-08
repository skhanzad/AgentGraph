"""Coder Agent: writes code per task spec, augmented with RAG retrieval."""
from __future__ import annotations

import hashlib
import json

from langchain_core.messages import SystemMessage, HumanMessage

from artifact_utils import clean_generated_content
from state import SoftwareAgentState
from llm import get_state_llm
from config import MAX_STALLED_REWORKS
from rag import build_rag_context, store_output, index_code


def _codebase_signature(code_artifacts: dict[str, str]) -> str:
    payload = json.dumps(code_artifacts, sort_keys=True, ensure_ascii=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def coder_node(state: SoftwareAgentState) -> SoftwareAgentState:
    llm = get_state_llm(state, temperature=0.2)
    task_list = state.get("task_list", [])
    code_artifacts = dict(state.get("code_artifacts") or {})
    generated_test_files = dict(state.get("generated_test_files") or {})
    implemented_task_ids = list(state.get("implemented_task_ids") or [])
    current_task_index = state.get("current_task_index", 0)
    architecture_doc = state.get("architecture_doc", "")
    tech_stack = state.get("tech_stack", "")
    review_feedback = state.get("review_feedback", "")
    patch_suggestion = state.get("patch_suggestion", "")

    # Rework mode: reviewer or debugger sent us back
    rework = bool(review_feedback or patch_suggestion)
    if rework:
        task_index = 0 if current_task_index >= len(task_list) else max(0, current_task_index - 1)
    else:
        task_index = current_task_index

    if task_index >= len(task_list):
        return {"current_code": state.get("current_code", ""), "next_node": "reviewer"}

    task = task_list[task_index]
    task_id = task.get("id", f"task_{task_index}")
    spec = task.get("spec", "")
    file_hint = task.get("file", "main.py")
    deps = task.get("deps", [])
    prior_file_content = code_artifacts.get(task_id, "")
    previous_signature = state.get("codebase_signature") or _codebase_signature(code_artifacts)

    # RAG: retrieve code patterns, architecture, and web API docs for the tech stack
    rag_ctx = build_rag_context(
        "coder",
        f"{spec} {file_hint}",
        web_query=f"{tech_stack} {spec} implementation example",
    )

    # Gather context from previously implemented tasks
    context_parts = [f"Architecture:\n{architecture_doc}"]
    context_parts.append(f"Task plan:\n{task_list}")
    for dep_id in deps:
        if dep_id in code_artifacts:
            context_parts.append(f"Existing code for {dep_id}:\n{code_artifacts[dep_id][:2000]}")
    if prior_file_content or task_id in code_artifacts:
        context_parts.append(f"Current content for {file_hint}:\n{prior_file_content[:4000]}")
    if review_feedback:
        context_parts.append(f"Review feedback to address:\n{review_feedback}")
    if patch_suggestion:
        context_parts.append(f"Debugger patch suggestion:\n{patch_suggestion}")
    if generated_test_files:
        rendered_tests = "\n\n".join(
            f"{path}:\n{content[:2000]}"
            for path, content in generated_test_files.items()
        )
        context_parts.append(f"Current executed tests:\n{rendered_tests}")
    if rag_ctx:
        context_parts.append(f"Retrieved reference material:\n{rag_ctx}")
    context = "\n\n---\n\n".join(context_parts)

    system = """You are a Software Engineer. Implement exactly what the task spec asks. Rules:
- Output only the code (or the content of the primary file). No markdown fences unless the spec asks for multiple files; then use clear filenames as comments.
- Follow the architecture and use existing code from context where relevant.
- Use the retrieved reference material (documentation, code patterns) to write correct, idiomatic code.
- If the feedback includes failing tests, rewrite the implementation so those tests pass.
- On rework, return the full replacement file content, not a diff.
- Prefer clear, runnable code. Include minimal docstrings and type hints if the language supports them."""

    messages = [
        SystemMessage(content=system),
        HumanMessage(content=f"Context:\n{context}\n\nTask id: {task_id}\nFile: {file_hint}\nSpec: {spec}\n\nProduce the code for this task."),
    ]
    response = llm.invoke(messages)
    code = response.content if hasattr(response, "content") else str(response)
    code = clean_generated_content(file_hint, code)

    code_artifacts[task_id] = code
    if task_id not in implemented_task_ids:
        implemented_task_ids.append(task_id)

    new_signature = _codebase_signature(code_artifacts)
    stalled_rework_count = 0 if new_signature != previous_signature else state.get("stalled_rework_count", 0)
    if rework and new_signature == previous_signature:
        stalled_rework_count = state.get("stalled_rework_count", 0) + 1

    # Store code in memory for RAG retrieval by reviewer/tester/debugger
    task_to_file = {t.get("id", ""): t.get("file", "") for t in task_list}
    store_output("coder", code, collection="codebase")
    index_code(code_artifacts, task_to_file)

    # Aggregate full code for single-file projects; multi-file we store per task
    full_code = "\n\n".join(code_artifacts.values())

    next_index = task_index + 1
    error = None
    if rework and stalled_rework_count >= MAX_STALLED_REWORKS:
        error = (
            f"Coder rework stalled for `{file_hint}` after {stalled_rework_count} unchanged attempts. "
            "The codebase did not converge."
        )
    return {
        "code_artifacts": code_artifacts,
        "implemented_task_ids": implemented_task_ids,
        "current_code": full_code,
        "current_task_index": next_index,
        "codebase_signature": new_signature,
        "stalled_rework_count": stalled_rework_count,
        "review_feedback": "",
        "patch_suggestion": "",
        "error": error,
    }
