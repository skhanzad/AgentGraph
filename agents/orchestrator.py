"""Orchestrator Agent: central coordinator, decomposes requirements, delegates."""
from langchain_core.messages import SystemMessage, HumanMessage

from state import SoftwareAgentState
from llm import get_llm


def orchestrator_node(state: SoftwareAgentState) -> SoftwareAgentState:
    llm = get_llm()
    user_request = state.get("user_request", "")

    system = """You are the Orchestrator of a multi-agent software team. Your job is to:
1. Parse the user's software request and clarify scope.
2. Produce a short project brief (2-4 paragraphs) that will be used by the Product Manager, Architect, and Planner.
Include: main goal, key features to build, non-goals, and any constraints (language, framework, deployment).
Output ONLY the project brief, no meta-commentary."""

    messages = [
        SystemMessage(content=system),
        HumanMessage(content=f"User request:\n{user_request}\n\nProduce the project brief."),
    ]
    response = llm.invoke(messages)
    project_brief = response.content if hasattr(response, "content") else str(response)

    return {
        "project_brief": project_brief,
        "delegated_plan": "pm -> architect -> planner -> coder -> reviewer -> tester -> docs -> devops",
    }
