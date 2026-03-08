"""Debugger Agent: edits the generated files after the coding pass."""
from __future__ import annotations

import hashlib
import json
import re

from langchain_core.messages import SystemMessage, HumanMessage

from artifact_utils import clean_generated_content
from state import SoftwareAgentState
from llm import get_state_llm


def _render_codebase(state: SoftwareAgentState) -> str:
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
    return "\n\n".join(sections)


def _extract_json_block(content: str) -> str:
    match = re.search(r"```json\s*\n(.*?)```", content, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    section = re.search(r"##\s*File Updates\s*\n(.*?)(?=\n##\s|\Z)", content, re.DOTALL | re.IGNORECASE)
    if section:
        return section.group(1).strip()
    return content.strip()


def _parse_file_updates(content: str) -> list[dict[str, str]]:
    raw = _extract_json_block(content)
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    updates: list[dict[str, str]] = []
    for item in parsed:
        if not isinstance(item, dict):
            continue
        path = str(item.get("file", "")).strip()
        body = str(item.get("content", ""))
        if path:
            updates.append({"file": path, "content": body})
    return updates


def _apply_updates(state: SoftwareAgentState, updates: list[dict[str, str]]) -> tuple[dict[str, str], list[str]]:
    task_list = state.get("task_list") or []
    path_to_task = {
        str(task.get("file", "")).strip(): str(task.get("id", "")).strip()
        for task in task_list
        if str(task.get("file", "")).strip()
    }
    code_artifacts = dict(state.get("code_artifacts") or {})
    applied_paths: list[str] = []
    for update in updates:
        path = update["file"]
        task_id = path_to_task.get(path)
        if not task_id:
            continue
        cleaned = clean_generated_content(path, update["content"])
        if cleaned:
            code_artifacts[task_id] = cleaned
            applied_paths.append(path)
    return code_artifacts, applied_paths


def _codebase_signature(code_artifacts: dict[str, str]) -> str:
    payload = json.dumps(code_artifacts, sort_keys=True, ensure_ascii=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def debugger_node(state: SoftwareAgentState) -> SoftwareAgentState:
    llm = get_state_llm(state)
    test_results = state.get("test_results", "")
    review_feedback = state.get("review_feedback", "")
    architecture_doc = state.get("architecture_doc", "")
    task_list = state.get("task_list", [])
    codebase = _render_codebase(state)

    system = """You are a Debugger performing a pre-review stabilization pass on a finished codebase.
Review the full file set and fix only concrete issues such as syntax problems, import mistakes, missing small glue code, dependency mismatches, or obvious inconsistencies with the architecture.
Do not rewrite the whole project if no fix is needed.

Output format:
## Analysis
1-3 short bullet points.

## File Updates
```json
[
  {"file": "path/to/file.py", "content": "full replacement file content"}
]
```

Use an empty JSON array if no edits are needed."""

    messages = [
        SystemMessage(content=system),
        HumanMessage(
            content=(
                f"Architecture:\n{architecture_doc}\n\n"
                f"Tasks:\n{task_list}\n\n"
                f"Codebase:\n{codebase}\n\n"
                f"Reviewer feedback from the prior cycle:\n{review_feedback}\n\n"
                f"Test results from the prior cycle:\n{test_results}\n\n"
                "Analyze the codebase and apply only targeted file fixes."
            )
        ),
    ]
    response = llm.invoke(messages)
    content = response.content if hasattr(response, "content") else str(response)
    updates = _parse_file_updates(content)
    code_artifacts, applied_paths = _apply_updates(state, updates)
    current_code = "\n\n".join(code_artifacts.values())
    patch_summary = ", ".join(applied_paths) if applied_paths else "No file edits applied."

    return {
        "failure_analysis": content,
        "patch_suggestion": "",
        "code_artifacts": code_artifacts,
        "current_code": current_code,
        "codebase_signature": _codebase_signature(code_artifacts),
        "debug_iteration": state.get("debug_iteration", 0) + 1,
    }
