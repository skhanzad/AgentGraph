"""Testing Agent: generates tests and executes them against the project."""
from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
import hashlib

from langchain_core.messages import SystemMessage, HumanMessage

from artifact_utils import clean_generated_content
from llm import get_state_llm
from project_writer import write_project
from state import SoftwareAgentState
from config import MAX_TEST_ITERATIONS


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


def _extract_section(content: str, header: str) -> str:
    match = re.search(rf"##\s*{re.escape(header)}\s*\n(.*?)(?=\n##\s|\Z)", content, re.DOTALL | re.IGNORECASE)
    return match.group(1).strip() if match else ""


def _looks_like_unittest_suite(code: str) -> bool:
    lowered = code.lower()
    return "import unittest" in lowered or "from unittest" in lowered or "unittest.testcase" in lowered


def _infer_primary_python_file(task_list: list[dict]) -> str:
    preferred = ("main.py", "app.py", "__main__.py", "cli.py", "server.py", "run.py")
    candidates = []
    for task in task_list:
        path = str(task.get("file", "")).strip()
        if not path.endswith(".py"):
            continue
        lower = path.lower()
        if lower.startswith("tests/") or "/tests/" in lower or os.path.basename(lower).startswith("test_"):
            continue
        candidates.append(path)
    for name in preferred:
        for path in candidates:
            if path.endswith(name):
                return path
    return candidates[0] if candidates else "main.py"


def _build_fallback_test_code(task_list: list[dict]) -> str:
    primary_file = _infer_primary_python_file(task_list)
    return f'''import py_compile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PRIMARY_FILE = PROJECT_ROOT / "{primary_file}"


class TestGeneratedProject(unittest.TestCase):
    def test_python_files_compile(self) -> None:
        failures: list[str] = []
        for path in PROJECT_ROOT.rglob("*.py"):
            if path.name.startswith("test_") or path.name.endswith("_test.py"):
                continue
            try:
                py_compile.compile(str(path), doraise=True)
            except py_compile.PyCompileError as exc:
                failures.append(f"{{path.relative_to(PROJECT_ROOT)}}: {{exc.msg}}")
        self.assertFalse(failures, "\\n".join(failures))

    def test_primary_file_exists(self) -> None:
        self.assertTrue(PRIMARY_FILE.exists(), f"Expected entry file {{PRIMARY_FILE}} to exist")


if __name__ == "__main__":
    unittest.main()
'''.strip()


def _prepare_generated_test_files(task_list: list[dict], content: str) -> dict[str, str]:
    test_path = _infer_test_file(task_list)
    extracted_test_code = clean_generated_content(test_path, _extract_test_section(content))
    if not extracted_test_code or not _looks_like_unittest_suite(extracted_test_code):
        extracted_test_code = _build_fallback_test_code(task_list)

    generated_test_files: dict[str, str] = {test_path: extracted_test_code}
    if test_path.startswith("tests/"):
        generated_test_files.setdefault("tests/__init__.py", "")
    return generated_test_files


def _materialize_project_for_testing(
    state: SoftwareAgentState,
    generated_test_files: dict[str, str],
) -> tuple[str, dict[str, str]]:
    project_dir = os.path.abspath(
        state.get("generated_project_dir") or state.get("output_dir") or tempfile.mkdtemp(prefix="agentgraph-tests-")
    )
    os.makedirs(project_dir, exist_ok=True)
    merged_test_files = dict(state.get("generated_test_files") or {})
    merged_test_files.update(generated_test_files)
    writable_state = dict(state)
    writable_state["generated_test_files"] = merged_test_files
    write_project(writable_state, project_dir)
    return project_dir, merged_test_files


def _run_unittest_suite(project_dir: str, test_files: dict[str, str]) -> tuple[bool, str]:
    env = os.environ.copy()
    existing_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = project_dir if not existing_pythonpath else project_dir + os.pathsep + existing_pythonpath
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    basenames = [os.path.basename(path) for path in test_files]
    patterns: list[str] = []
    if any(name.startswith("test") for name in basenames):
        patterns.append("test*.py")
    if any(name.endswith("_test.py") for name in basenames):
        patterns.append("*_test.py")
    if not patterns:
        patterns.append("test*.py")

    outputs: list[str] = []
    any_tests_ran = False
    overall_passed = True
    for pattern in patterns:
        command = [sys.executable, "-m", "unittest", "discover", "-s", ".", "-p", pattern, "-v"]
        completed = subprocess.run(
            command,
            cwd=project_dir,
            capture_output=True,
            text=True,
            timeout=120,
            env=env,
        )
        output = "\n".join(
            part
            for part in [
                f"$ {' '.join(command)}",
                completed.stdout.strip(),
                completed.stderr.strip(),
            ]
            if part
        ).strip()
        outputs.append(output)
        if "Ran 0 tests" not in output:
            any_tests_ran = True
        if completed.returncode != 0:
            overall_passed = False

    if not any_tests_ran:
        overall_passed = False
        outputs.append("No tests were collected by unittest discovery.")

    return overall_passed, "\n\n".join(outputs).strip()


def tester_node(state: SoftwareAgentState) -> SoftwareAgentState:
    llm = get_state_llm(state)
    current_code = state.get("current_code", "")
    architecture_doc = state.get("architecture_doc", "")
    tech_stack = state.get("tech_stack", "")
    test_iteration = state.get("test_iteration", 0)
    task_list = state.get("task_list", [])

    system = """You are a QA Engineer. Given the code and tech stack:
1. Propose a short test plan (unit or integration) as bullet points.
2. Write 1-3 small Python tests using only the standard library `unittest` module. The test code must be self-contained and runnable. Do not rely on pytest fixtures, plugins, markers, or third-party test helpers.
3. Focus on deterministic tests that import the generated modules using the planned file structure. Do NOT use placeholder imports.
4. Do not simulate the result. The tests will be executed after generation.

Output format:
## Test Plan
- ...

## Test Code
```python
import unittest
...
```
"""

    messages = [
        SystemMessage(content=system),
        HumanMessage(
            content=(
                f"Tech stack:\n{tech_stack}\n\n"
                f"Architecture:\n{architecture_doc}\n\n"
                f"Code:\n{current_code}\n\n"
                "Produce a test plan and runnable unittest code."
            )
        ),
    ]
    response = llm.invoke(messages)
    content = response.content if hasattr(response, "content") else str(response)
    generated_test_files = _prepare_generated_test_files(task_list, content)
    project_dir, generated_test_files = _materialize_project_for_testing(state, generated_test_files)
    test_passed, execution_output = _run_unittest_suite(project_dir, generated_test_files)

    test_plan = _extract_section(content, "Test Plan") or "- Execute the generated unittest suite against the materialized project."
    primary_test_path = next(iter(generated_test_files), "tests/test_generated.py")
    executed_test_code = generated_test_files.get(primary_test_path, "")
    result_summary = "All executed tests passed." if test_passed else "Executed tests failed."
    report = "\n\n".join(
        [
            "## Test Plan\n" + test_plan,
            "## Test Code\n```python\n" + executed_test_code.strip() + "\n```",
            "## Result\n" + result_summary,
            "## Output\n```text\n" + execution_output.strip() + "\n```",
        ]
    ).strip()

    feedback = ""
    error = None
    failure_signature = state.get("test_failure_signature", "")
    if not test_passed:
        current_failure_signature = hashlib.sha256(execution_output.encode("utf-8")).hexdigest()
        feedback = (
            "Reimplement the project so the executed test suite passes.\n\n"
            f"Test file: {primary_test_path}\n\n"
            f"Execution output:\n{execution_output}"
        )
        failure_signature = current_failure_signature
        if test_iteration >= MAX_TEST_ITERATIONS - 1:
            error = (
                f"Tests did not converge after {MAX_TEST_ITERATIONS} iterations.\n\n"
                f"Last failing output:\n{execution_output}"
            )
    else:
        failure_signature = ""

    return {
        "test_code": report,
        "test_results": execution_output,
        "test_passed": test_passed,
        "test_iteration": test_iteration + 1,
        "test_failure_signature": failure_signature,
        "generated_test_files": generated_test_files,
        "generated_project_dir": project_dir,
        "current_task_index": state.get("current_task_index", 0) if test_passed else 0,
        "review_feedback": feedback,
        "error": error,
    }
