"""Shared state for the multi-agent software pipeline."""
from typing import TypedDict, Optional, Any


class SoftwareAgentState(TypedDict, total=False):
    """State passed through the LangGraph. All fields optional for incremental updates."""

    # User input
    user_request: str

    # Orchestrator
    project_brief: str
    delegated_plan: str

    # Product Manager
    prd: str
    user_stories: str
    acceptance_criteria: str

    # Architect
    architecture_doc: str
    tech_stack: str
    api_design: str
    file_structure: str

    # Planner
    task_list: list[dict[str, Any]]  # [{id, spec, deps, ...}, ...]
    task_dag: str

    # Coder
    current_task_index: int
    code_artifacts: dict[str, str]  # task_id -> code or file_path -> content
    current_code: str
    implemented_task_ids: list[str]

    # Reviewer
    review_feedback: str
    review_passed: bool
    review_iteration: int

    # Tester
    test_code: str
    test_results: str
    test_passed: bool
    test_iteration: int

    # Debugger
    failure_analysis: str
    patch_suggestion: str
    debug_iteration: int

    # Documentation
    readme: str
    api_docs: str
    inline_docs: str

    # DevOps
    dockerfile: str
    cicd_config: str
    run_instructions: str

    # Control / routing
    next_node: Optional[str]
    error: Optional[str]
    done: bool
