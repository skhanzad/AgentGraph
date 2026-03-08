"""Product Manager Agent: PRD, user stories, acceptance criteria."""
from langchain_core.messages import SystemMessage, HumanMessage

from state import SoftwareAgentState
from llm import get_llm


def pm_node(state: SoftwareAgentState) -> SoftwareAgentState:
    llm = get_llm()
    project_brief = state.get("project_brief", "")
    user_request = state.get("user_request", "")

    system = """You are a Product Manager. Given a project brief, produce:
1. PRD (Product Requirements Document): 3-6 bullet points of high-level requirements.
2. User stories: 3-8 short user stories in format "As a [role], I want [feature] so that [benefit]."
3. Acceptance criteria: 2-4 criteria that define "done" for the project.

Output in this exact structure (use the headers):

## PRD
- ...

## User Stories
- ...

## Acceptance Criteria
- ..."""

    messages = [
        SystemMessage(content=system),
        HumanMessage(content=f"Project brief:\n{project_brief}\n\nOriginal request: {user_request}\n\nProduce PRD, user stories, and acceptance criteria."),
    ]
    response = llm.invoke(messages)
    content = response.content if hasattr(response, "content") else str(response)

    # Split roughly for state (optional; we can store as one block)
    prd = content
    return {
        "prd": prd,
        "user_stories": prd,
        "acceptance_criteria": prd,
    }
