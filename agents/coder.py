"""Coder Agent: writes code per task spec."""
from langchain_core.messages import SystemMessage, HumanMessage

from state import SoftwareAgentState
from llm import get_llm


def coder_node(state: SoftwareAgentState) -> SoftwareAgentState:
    llm = get_llm(temperature=0.2)
    task_list = state.get("task_list", [])
    code_artifacts = dict(state.get("code_artifacts") or {})
    implemented_task_ids = list(state.get("implemented_task_ids") or [])
    current_task_index = state.get("current_task_index", 0)
    architecture_doc = state.get("architecture_doc", "")
    review_feedback = state.get("review_feedback", "")
    patch_suggestion = state.get("patch_suggestion", "")

    # Rework mode: reviewer or debugger sent us back
    rework = bool(review_feedback or patch_suggestion)
    if rework:
        task_index = max(0, current_task_index - 1)
    else:
        task_index = current_task_index

    if task_index >= len(task_list):
        return {"current_code": state.get("current_code", ""), "next_node": "reviewer"}

    task = task_list[task_index]
    task_id = task.get("id", f"task_{task_index}")
    spec = task.get("spec", "")
    file_hint = task.get("file", "main.py")
    deps = task.get("deps", [])

    # Gather context from previously implemented tasks
    context_parts = [f"Architecture:\n{architecture_doc}"]
    for dep_id in deps:
        if dep_id in code_artifacts:
            context_parts.append(f"Existing code for {dep_id}:\n{code_artifacts[dep_id][:2000]}")
    if review_feedback:
        context_parts.append(f"Review feedback to address:\n{review_feedback}")
    if patch_suggestion:
        context_parts.append(f"Debugger patch suggestion:\n{patch_suggestion}")
    context = "\n\n---\n\n".join(context_parts)

    system = """You are a Software Engineer. Implement exactly what the task spec asks. Rules:
- Output only the code (or the content of the primary file). No markdown fences unless the spec asks for multiple files; then use clear filenames as comments.
- Follow the architecture and use existing code from context where relevant.
- Prefer clear, runnable code. Include minimal docstrings and type hints if the language supports them."""

    messages = [
        SystemMessage(content=system),
        HumanMessage(content=f"Context:\n{context}\n\nTask id: {task_id}\nFile: {file_hint}\nSpec: {spec}\n\nProduce the code for this task."),
    ]
    response = llm.invoke(messages)
    code = response.content if hasattr(response, "content") else str(response)
    code = code.strip()
    if code.startswith("```"):
        lines = code.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        code = "\n".join(lines)

    code_artifacts[task_id] = code
    if task_id not in implemented_task_ids:
        implemented_task_ids.append(task_id)

    # Aggregate full code for single-file projects; multi-file we store per task
    full_code = "\n\n".join(code_artifacts.values())

    next_index = task_index + 1
    return {
        "code_artifacts": code_artifacts,
        "implemented_task_ids": implemented_task_ids,
        "current_code": full_code,
        "current_task_index": next_index,
        "review_feedback": "",
        "patch_suggestion": "",
    }
