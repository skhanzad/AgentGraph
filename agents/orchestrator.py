"""Orchestrator Agent: central coordinator, decomposes requirements, delegates."""
from langchain_core.messages import SystemMessage, HumanMessage

from state import SoftwareAgentState
from llm import get_state_llm
from rag import build_rag_context, store_output


def orchestrator_node(state: SoftwareAgentState) -> SoftwareAgentState:
    llm = get_state_llm(state)
    user_request = state.get("user_request", "")

    rag_ctx = build_rag_context("orchestrator", user_request)

    system = """You are the Orchestrator of a multi-agent software team. Your job is to:
1. Parse the user's software request and clarify scope.
2. Produce a short project brief (2-4 paragraphs) that will be used by the Product Manager, Architect, and Planner.
Include: main goal, key features to build, non-goals, and any constraints (language, framework, deployment).
Output ONLY the project brief, no meta-commentary."""

    human = f"User request:\n{user_request}"
    if rag_ctx:
        human += f"\n\nContext from knowledge base:\n{rag_ctx}"
    human += "\n\nProduce the project brief."

    messages = [SystemMessage(content=system), HumanMessage(content=human)]
    response = llm.invoke(messages)
    project_brief = response.content if hasattr(response, "content") else str(response)

    store_output("orchestrator", project_brief, collection="episodic")

    return {
        "project_brief": project_brief,
        "delegated_plan": "orchestrator_intake -> [pm || architect] -> planner -> coder -> reviewer -> tester -> orchestrator_release -> [docs || devops] -> project_writer -> git",
        "orchestration_phase": "design_parallel",
    }


def orchestrator_release_node(state: SoftwareAgentState) -> SoftwareAgentState:
    """Mark the release/documentation phase before parallel docs/devops work."""
    return {
        "orchestration_phase": "release_parallel",
    }
