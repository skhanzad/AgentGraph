"""Build and compile the multi-agent software pipeline as a LangGraph."""
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from state import SoftwareAgentState
from agents import (
    orchestrator_node,
    pm_node,
    architect_node,
    planner_node,
    coder_node,
    reviewer_node,
    tester_node,
    debugger_node,
    docs_node,
    devops_node,
    docker_tester_node,
)


def _route_after_coder(state: SoftwareAgentState) -> str:
    """After coder: docker-test loop -> docker_tester; more tasks -> coder; else -> reviewer."""
    if state.get("docker_test_phase"):
        return "docker_tester"
    task_list = state.get("task_list") or []
    current = state.get("current_task_index", 0)
    if current < len(task_list):
        return "coder"
    return "reviewer"


def _route_after_reviewer(state: SoftwareAgentState) -> str:
    """After reviewer: rejected -> coder (rework); approved -> tester."""
    if state.get("review_passed"):
        return "tester"
    return "coder"


def _route_after_tester(state: SoftwareAgentState) -> str:
    """After tester: failed -> debugger; passed -> docs."""
    if state.get("test_passed"):
        return "docs"
    return "debugger"


def _route_after_docker_tester(state: SoftwareAgentState) -> str:
    """After docker_tester: passed -> END; failed -> debugger for fix loop."""
    if state.get("docker_test_passed"):
        return END
    return "debugger"


def build_graph():
    graph = StateGraph(SoftwareAgentState)

    graph.add_node("orchestrator", orchestrator_node)
    graph.add_node("pm", pm_node)
    graph.add_node("architect", architect_node)
    graph.add_node("planner", planner_node)
    graph.add_node("coder", coder_node)
    graph.add_node("reviewer", reviewer_node)
    graph.add_node("tester", tester_node)
    graph.add_node("debugger", debugger_node)
    graph.add_node("docs", docs_node)
    graph.add_node("devops", devops_node)
    graph.add_node("docker_tester", docker_tester_node)

    graph.set_entry_point("orchestrator")
    graph.add_edge("orchestrator", "pm")
    graph.add_edge("pm", "architect")
    graph.add_edge("architect", "planner")
    graph.add_edge("planner", "coder")

    graph.add_conditional_edges("coder", _route_after_coder)
    graph.add_conditional_edges("reviewer", _route_after_reviewer)
    graph.add_conditional_edges("tester", _route_after_tester)
    graph.add_edge("debugger", "coder")
    graph.add_edge("docs", "devops")
    graph.add_edge("devops", "docker_tester")
    graph.add_conditional_edges("docker_tester", _route_after_docker_tester)

    return graph.compile(checkpointer=MemorySaver())


def get_graph():
    return build_graph()
