"""Planner Agent: break work into atomic tasks with dependency DAG."""
from langchain_core.messages import SystemMessage, HumanMessage
import json
import re

from state import SoftwareAgentState
from llm import get_llm
from rag import build_rag_context, store_output


def planner_node(state: SoftwareAgentState) -> SoftwareAgentState:
    llm = get_llm()
    architecture_doc = state.get("architecture_doc", "")
    file_structure = state.get("file_structure", "")
    prd = state.get("prd", "")
    project_brief = state.get("project_brief", "")
    planning_input = prd or project_brief

    rag_ctx = build_rag_context("planner", f"{architecture_doc[:300]} task planning")

    system = """You are a Task Planner. Given the architecture and file structure, produce tasks that together form the ENTIRE codebase as a shippable package. Every file in the File Structure must be covered by exactly one task.

Each task must have:
- "id": string, e.g. "task_1", "task_2"
- "spec": string, what to implement (one clear deliverable for that file)
- "deps": array of task ids that must be done before this one (e.g. ["task_1"])
- "file": string, path to the file to create (must match the File Structure)

Include tasks for:
1. Dependency file first: requirements.txt (Python) or pyproject.toml, or equivalent for other languages.
2. Package/root __init__.py if the layout has packages.
3. Main entry point and all source modules.
4. Test file(s).
Do NOT include Dockerfile or CI config—DevOps will add those later.

Example for a Python app:
[
  {"id": "task_1", "spec": "Create requirements.txt with all project dependencies", "deps": [], "file": "requirements.txt"},
  {"id": "task_2", "spec": "Create main entry point", "deps": ["task_1"], "file": "src/main.py"},
  {"id": "task_3", "spec": "Create tests for main", "deps": ["task_2"], "file": "tests/test_main.py"}
]

Output ONLY the JSON array, no markdown or explanation. Order tasks so dependencies come first. Every file in the architecture's File Structure must appear as a task's "file"."""

    human = f"Architecture:\n{architecture_doc}\n\nFile structure:\n{file_structure}\n\nPRD / Brief:\n{planning_input}"
    if rag_ctx:
        human += f"\n\nRetrieved context:\n{rag_ctx}"
    human += "\n\nProduce the task list as JSON array."

    messages = [SystemMessage(content=system), HumanMessage(content=human)]
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

    store_output("planner", content, collection="episodic")

    return {
        "task_list": task_list,
        "task_dag": content,
        "current_task_index": 0,
        "code_artifacts": {},
        "implemented_task_ids": [],
    }
