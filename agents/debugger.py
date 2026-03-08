"""Debugger Agent: analyzes failures and suggests patches."""
from langchain_core.messages import SystemMessage, HumanMessage

from state import SoftwareAgentState
from llm import get_state_llm


def debugger_node(state: SoftwareAgentState) -> SoftwareAgentState:
    llm = get_state_llm(state)
    test_results = state.get("test_results", "")
    current_code = state.get("current_code", "")

    system = """You are a Debugger. Given the test failure (or error) and the current code:
1. State the likely root cause in 1-2 sentences.
2. Propose a concrete patch: output the corrected code snippet or the exact changes needed (you can output full file or diff-style).

Your output will be fed back to the Coder to apply the fix. Be specific."""

    messages = [
        SystemMessage(content=system),
        HumanMessage(content=f"Test results / failure:\n{test_results}\n\nCurrent code:\n{current_code}\n\nRoot cause and patch:"),
    ]
    response = llm.invoke(messages)
    content = response.content if hasattr(response, "content") else str(response)

    return {
        "failure_analysis": content,
        "patch_suggestion": content,
        "debug_iteration": state.get("debug_iteration", 0) + 1,
    }
