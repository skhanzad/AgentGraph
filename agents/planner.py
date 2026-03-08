"""Planner Agent: break work into atomic tasks with dependency DAG."""
from langchain_core.messages import SystemMessage, HumanMessage
import json
import re

from state import SoftwareAgentState
from llm import get_llm


def planner_node(state: SoftwareAgentState) -> SoftwareAgentState:
    llm = get_llm()
    architecture_doc = state.get("architecture_doc", "")
    file_structure = state.get("file_structure", "")
    prd = state.get("prd", "")

    system = """You are a Task Planner. Given the architecture and file structure, break the project into atomic coding tasks.
Output a JSON array of tasks. Each task must have:
- "id": string, e.g. "task_1", "task_2"
- "spec": string, what to implement (one clear deliverable)
- "deps": array of task ids that must be done before this one (e.g. ["task_1"])
- "file": string, primary file to create or modify (e.g. "src/main.py")

Example:
[
  {"id": "task_1", "spec": "Create project skeleton and main entry point", "deps": [], "file": "src/main.py"},
  {"id": "task_2", "spec": "Implement core logic module", "deps": ["task_1"], "file": "src/core.py"}
]

Output ONLY the JSON array, no markdown or explanation. Order tasks so dependencies come first."""

    messages = [
        SystemMessage(content=system),
        HumanMessage(content=f"Architecture:\n{architecture_doc}\n\nFile structure:\n{file_structure}\n\nPRD:\n{prd}\n\nProduce the task list as JSON array."),
    ]
    response = llm.invoke(messages)
    content = response.content if hasattr(response, "content") else str(response)
    content = content.strip()
    # Strip markdown code block if present
    if content.startswith("```"):
        content = re.sub(r"^```\w*\n?", "", content)
        content = re.sub(r"\n?```\s*$", "", content)
    try:
        task_list = json.loads(content)
        if not isinstance(task_list, list):
            task_list = [{"id": "task_1", "spec": "Implement project per architecture", "deps": [], "file": "src/main.py"}]
    except json.JSONDecodeError:
        task_list = [{"id": "task_1", "spec": "Implement project per architecture", "deps": [], "file": "src/main.py"}]

    return {
        "task_list": task_list,
        "task_dag": content,
        "current_task_index": 0,
        "code_artifacts": {},
        "implemented_task_ids": [],
    }
