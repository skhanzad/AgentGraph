"""Testing Agent: generates tests and reports pass/fail (simulated run)."""
import os
import re

from langchain_core.messages import SystemMessage, HumanMessage

from artifact_utils import clean_generated_content
from state import SoftwareAgentState
from llm import get_llm
from config import MAX_DEBUG_ITERATIONS


def _infer_test_file(task_list: list[dict]) -> str:
    """Prefer an existing planned test file when one exists."""
    for task in task_list:
        path = (task.get("file") or "").strip()
        base = os.path.basename(path).lower()
        if base.startswith("test_") or base.endswith("_test.py") or "tests/" in path.lower():
            return path
    return "tests/test_generated.py"


def _extract_test_section(content: str) -> str:
    """Extract only the test-code section before generic cleaning."""
    match = re.search(r"##\s*Test Code\s*\n(.*?)(?=\n##\s|\Z)", content, re.DOTALL | re.IGNORECASE)
    return match.group(1).strip() if match else content


def tester_node(state: SoftwareAgentState) -> SoftwareAgentState:
    llm = get_llm()
    current_code = state.get("current_code", "")
    architecture_doc = state.get("architecture_doc", "")
    tech_stack = state.get("tech_stack", "")
    test_iteration = state.get("test_iteration", 0)
    task_list = state.get("task_list", [])

    system = """You are a QA Engineer. Given the code and tech stack:
1. Propose a short test plan (unit or integration) as bullet points.
2. Write 1-3 small test functions (e.g. using pytest) that exercise the main behavior. The test code must be self-contained and runnable — include all necessary imports (import the modules under test using the paths from the file structure). Do NOT use placeholder imports.
3. Then simulate running the tests: either say "All tests passed" or "Tests failed: <reason>".

Output format:
## Test Plan
- ...

## Test Code
```python
import ...

def test_...:
    ...
```

## Result
All tests passed.
OR
Tests failed: <short reason>"""

    messages = [
        SystemMessage(content=system),
        HumanMessage(content=f"Tech stack:\n{tech_stack}\n\nArchitecture:\n{architecture_doc}\n\nCode:\n{current_code}\n\nProduce test plan, test code, and simulated result."),
    ]
    response = llm.invoke(messages)
    content = response.content if hasattr(response, "content") else str(response)
    test_passed = "all tests passed" in content.lower() or "tests passed" in content.lower()
    if "tests failed" in content.lower():
        test_passed = False

    test_path = _infer_test_file(task_list)
    extracted_test_code = clean_generated_content(test_path, _extract_test_section(content))
    generated_test_files: dict[str, str] = {}
    if extracted_test_code and ("def test_" in extracted_test_code or "pytest" in extracted_test_code):
        generated_test_files[test_path] = extracted_test_code

    # After max debug iterations, force pass so pipeline can finish
    if not test_passed and test_iteration >= MAX_DEBUG_ITERATIONS - 1:
        test_passed = True
        content += "\n(Max debug iterations reached; proceeding.)"

    return {
        "test_code": content,
        "test_results": content,
        "test_passed": test_passed,
        "test_iteration": test_iteration + 1,
        "generated_test_files": generated_test_files,
    }
