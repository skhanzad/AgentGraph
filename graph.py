"""Build and compile the multi-agent software pipeline as a LangGraph."""
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from state import SoftwareAgentState
from agents import (
    orchestrator_node,
    orchestrator_release_node,
    pm_node,
    architect_node,
    planner_node,
    coder_node,
    reviewer_node,
    tester_node,
    debugger_node,
    docs_node,
    devops_node,
    project_writer_node,
    git_node,
)


def _route_after_coder(state: SoftwareAgentState) -> str:
    """After coder: more tasks -> coder; else -> project_writer."""
    task_list = state.get("task_list") or []
    current = state.get("current_task_index", 0)
    if current < len(task_list):
        return "coder"
    return "project_writer"


def _route_after_reviewer(state: SoftwareAgentState) -> str:
    """After reviewer: rejected -> coder (rework); approved -> tester."""
    if state.get("review_passed"):
        return "tester"
    return "coder"


def _route_after_tester(state: SoftwareAgentState) -> str:
    """After tester: failed -> coder; passed -> orchestrator_release."""
    if state.get("test_passed"):
        return "orchestrator_release"
    return "coder"


def _route_after_git(state: SoftwareAgentState) -> str:
    """After git: release snapshots end the graph; code snapshots go to review."""
    if state.get("orchestration_phase") == "release_parallel":
        return END
    return "reviewer"


def build_graph():
    graph = StateGraph(SoftwareAgentState)

    graph.add_node("orchestrator", orchestrator_node)
    graph.add_node("orchestrator_release", orchestrator_release_node)
    graph.add_node("pm", pm_node)
    graph.add_node("architect", architect_node)
    graph.add_node("planner", planner_node)
    graph.add_node("coder", coder_node)
    graph.add_node("reviewer", reviewer_node)
    graph.add_node("tester", tester_node)
    graph.add_node("debugger", debugger_node)
    graph.add_node("docs", docs_node)
    graph.add_node("devops", devops_node)
    graph.add_node("project_writer", project_writer_node)
    graph.add_node("git", git_node)

    graph.set_entry_point("orchestrator")
    graph.add_edge("orchestrator", "pm")
    graph.add_edge("orchestrator", "architect")
    graph.add_edge("pm", "planner")
    graph.add_edge("architect", "planner")
    graph.add_edge("planner", "coder")

    graph.add_conditional_edges("coder", _route_after_coder)
    graph.add_conditional_edges("reviewer", _route_after_reviewer)
    graph.add_conditional_edges("tester", _route_after_tester)
    graph.add_edge("debugger", "coder")
    graph.add_edge("orchestrator_release", "docs")
    graph.add_edge("orchestrator_release", "devops")
    graph.add_edge("docs", "project_writer")
    graph.add_edge("devops", "project_writer")
    graph.add_edge("project_writer", "git")
    graph.add_conditional_edges("git", _route_after_git)

    return graph.compile(checkpointer=MemorySaver())


def get_graph():
    return build_graph()
