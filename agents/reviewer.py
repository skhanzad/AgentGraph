"""Code Reviewer Agent: quality gate, can reject and send back to Coder."""
from langchain_core.messages import SystemMessage, HumanMessage

from state import SoftwareAgentState
from llm import get_llm
from config import MAX_REVIEW_ITERATIONS


def reviewer_node(state: SoftwareAgentState) -> SoftwareAgentState:
    llm = get_llm()
    current_code = state.get("current_code", "")
    architecture_doc = state.get("architecture_doc", "")
    task_list = state.get("task_list", [])
    review_iteration = state.get("review_iteration", 0)

    system = """You are a Code Reviewer. Review the code for:
1. Correctness and alignment with the architecture.
2. Obvious bugs, security issues, or bad practices.
3. Readability and style.

If the code is acceptable, respond with exactly: APPROVED
Otherwise, respond with REJECTED followed by a short bullet list of required changes (no code, just what to fix)."""

    messages = [
        SystemMessage(content=system),
        HumanMessage(content=f"Architecture:\n{architecture_doc}\n\nTasks:\n{task_list}\n\nCode to review:\n{current_code}\n\nVerdict (APPROVED or REJECTED + feedback):"),
    ]
    response = llm.invoke(messages)
    content = (response.content if hasattr(response, "content") else str(response)).strip().upper()
    passed = "APPROVED" in content and "REJECTED" not in content[:20]
    feedback = "" if passed else (response.content if hasattr(response, "content") else str(response))

    # Cap iterations
    if not passed and review_iteration >= MAX_REVIEW_ITERATIONS - 1:
        passed = True
        feedback = "(Max review iterations reached; proceeding.)"

    return {
        "review_feedback": feedback,
        "review_passed": passed,
        "review_iteration": review_iteration + 1,
    }
