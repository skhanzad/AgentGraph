"""Product Manager Agent: PRD, user stories, acceptance criteria."""
import re

from langchain_core.messages import SystemMessage, HumanMessage

from state import SoftwareAgentState
from llm import get_llm
from rag import build_rag_context, store_output


def _extract_section(doc: str, header: str) -> str:
    """Extract content under a ## header, up to the next ## or end of doc."""
    pattern = rf"##\s*{re.escape(header)}\s*\n(.*?)(?=\n##\s|\Z)"
    match = re.search(pattern, doc, re.DOTALL | re.IGNORECASE)
    return match.group(1).strip() if match else ""


def pm_node(state: SoftwareAgentState) -> SoftwareAgentState:
    llm = get_llm()
    project_brief = state.get("project_brief", "")
    user_request = state.get("user_request", "")

    rag_ctx = build_rag_context("pm", f"{user_request} {project_brief[:200]}")

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

    human = f"Project brief:\n{project_brief}\n\nOriginal request: {user_request}"
    if rag_ctx:
        human += f"\n\nContext from knowledge base:\n{rag_ctx}"
    human += "\n\nProduce PRD, user stories, and acceptance criteria."

    messages = [SystemMessage(content=system), HumanMessage(content=human)]
    response = llm.invoke(messages)
    content = response.content if hasattr(response, "content") else str(response)

    store_output("pm", content, collection="episodic")

    # Parse individual sections so they are stored separately
    user_stories = _extract_section(content, "User Stories")
    acceptance_criteria = _extract_section(content, "Acceptance Criteria")

    return {
        "prd": content,
        "user_stories": user_stories,
        "acceptance_criteria": acceptance_criteria,
    }
