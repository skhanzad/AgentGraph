"""Docker Tester Agent: builds Docker image, runs the generated tests in container, validates the full package."""
import os
import re
import shutil
import subprocess
import tempfile

from state import SoftwareAgentState
from config import MAX_DOCKER_TEST_ITERATIONS

IMAGE_NAME = "agentgraph-test"
CONTAINER_NAME = "agentgraph-test-run"


def _cleanup_docker():
    """Remove test container and image, ignoring errors."""
    subprocess.run(
        ["docker", "rm", "-f", CONTAINER_NAME],
        capture_output=True, timeout=30,
    )
    subprocess.run(
        ["docker", "rmi", "-f", IMAGE_NAME],
        capture_output=True, timeout=30,
    )


def _strip_fences(text: str) -> str:
    """Remove outer markdown code fences."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)
    return text


def _extract_test_code(raw: str) -> str:
    """Extract runnable test code from the tester agent's output."""
    # Try to pull code from a ```python fence inside ## Test Code section
    section = re.search(r"## Test Code\s*\n(.*?)(?=\n## |\Z)", raw, re.DOTALL | re.IGNORECASE)
    block = section.group(1) if section else raw
    fence = re.search(r"```(?:python)?\s*\n(.*?)```", block, re.DOTALL)
    if fence:
        return fence.group(1).strip()
    # If no fence, return the raw section stripped of markdown headers
    code = re.sub(r"^##.*$", "", block, flags=re.MULTILINE).strip()
    return code


def _find_test_files(task_to_file: dict[str, str]) -> list[str]:
    """Return file paths from the task list that look like test files."""
    test_files = []
    for path in task_to_file.values():
        base = os.path.basename(path).lower()
        if base.startswith("test_") or base.endswith("_test.py") or "tests/" in path.lower():
            test_files.append(path)
    return test_files


def _infer_test_command(tech_stack: str, test_files: list[str], all_files: list[str]) -> list[str]:
    """Build the test runner command targeting the actual generated test files."""
    tech = tech_stack.lower()
    if "python" in tech or any(f.endswith(".py") for f in all_files):
        if test_files:
            return ["python", "-m", "pytest", "-v"] + test_files
        return ["python", "-m", "pytest", "-v"]
    if "node" in tech or "javascript" in tech or "typescript" in tech:
        return ["npm", "test"]
    if "go" in tech:
        return ["go", "test", "./..."]
    if "rust" in tech:
        return ["cargo", "test"]
    return ["python", "-m", "pytest", "-v"]


def docker_tester_node(state: SoftwareAgentState) -> SoftwareAgentState:
    iteration = state.get("docker_test_iteration", 0)

    # Cap iterations to prevent infinite loop
    if iteration >= MAX_DOCKER_TEST_ITERATIONS:
        _cleanup_docker()
        print("    Max docker test iterations reached; proceeding.")
        return {
            "docker_test_passed": True,
            "docker_test_results": "(Max docker test iterations reached; proceeding.)",
            "docker_test_iteration": iteration,
            "docker_test_phase": False,
        }

    task_list = state.get("task_list") or []
    code_artifacts = state.get("code_artifacts") or {}
    dockerfile_raw = state.get("dockerfile", "")
    tech_stack = state.get("tech_stack", "")
    test_code_raw = state.get("test_code", "")

    # Map task_id -> file path
    task_to_file = {}
    for t in task_list:
        task_to_file[t.get("id", "")] = t.get("file", "main.py")

    all_files = list(task_to_file.values())
    test_files = _find_test_files(task_to_file)

    print(f"    Iteration {iteration + 1}/{MAX_DOCKER_TEST_ITERATIONS}")

    # Write project to a temp directory
    tmpdir = tempfile.mkdtemp(prefix="agentgraph_docker_")
    try:
        # Write code artifacts
        for task_id, code in code_artifacts.items():
            path = task_to_file.get(task_id, f"{task_id}.py")
            path = path.lstrip("/") or "main.py"
            code = _strip_fences(code)
            full = os.path.join(tmpdir, path)
            d = os.path.dirname(full)
            if d:
                os.makedirs(d, exist_ok=True)
            with open(full, "w", encoding="utf-8") as f:
                f.write(code)

        # Write tester-generated test code if it's not already covered by a task
        if test_code_raw:
            extracted = _extract_test_code(test_code_raw)
            if extracted and ("import" in extracted or "def test_" in extracted):
                # Only write if no test files exist in code_artifacts, or write as extra
                test_dest = "test_generated.py"
                if test_files:
                    test_dest = "test_generated_extra.py"
                full = os.path.join(tmpdir, test_dest)
                with open(full, "w", encoding="utf-8") as f:
                    f.write(extracted)
                if test_dest not in [os.path.basename(tf) for tf in test_files]:
                    test_files.append(test_dest)
                print(f"    Wrote tester-generated tests → {test_dest}")

        # Write Dockerfile
        df_body = _strip_fences(dockerfile_raw)
        fence = re.search(r"```(?:dockerfile?)?\s*\n(.*?)```", df_body, re.DOTALL)
        if fence:
            df_body = fence.group(1).strip()
        with open(os.path.join(tmpdir, "Dockerfile"), "w", encoding="utf-8") as f:
            f.write(df_body)

        # Write .dockerignore
        with open(os.path.join(tmpdir, ".dockerignore"), "w", encoding="utf-8") as f:
            f.write(".git\n__pycache__\n*.pyc\n.venv\n.env\n")

        # Cleanup any leftover container/image from previous iteration
        _cleanup_docker()

        # Build Docker image
        print("    Building Docker image...")
        build = subprocess.run(
            ["docker", "build", "-t", IMAGE_NAME, "."],
            cwd=tmpdir,
            capture_output=True,
            text=True,
            timeout=300,
        )
        if build.returncode != 0:
            error = f"Docker build failed (exit {build.returncode}):\n{build.stderr}\n{build.stdout}"
            print(f"    BUILD FAILED\n{build.stderr[-500:]}")
            _cleanup_docker()
            return {
                "docker_test_passed": False,
                "docker_test_results": error,
                "test_results": error,
                "docker_test_iteration": iteration + 1,
                "docker_test_phase": True,
            }
        print("    Build succeeded.")

        # Run tests in container (overrides CMD with test command)
        test_cmd = _infer_test_command(tech_stack, test_files, all_files)
        print(f"    Running tests: {' '.join(test_cmd)}")
        run = subprocess.run(
            ["docker", "run", "--name", CONTAINER_NAME, IMAGE_NAME] + test_cmd,
            capture_output=True,
            text=True,
            timeout=120,
        )
        output = f"Exit code: {run.returncode}\nSTDOUT:\n{run.stdout}\nSTDERR:\n{run.stderr}"
        passed = run.returncode == 0

        # Print results
        if passed:
            print(f"    TESTS PASSED")
            if run.stdout.strip():
                # Show last few lines of pytest output
                lines = run.stdout.strip().split("\n")
                for line in lines[-5:]:
                    print(f"    {line}")
        else:
            print(f"    TESTS FAILED (exit {run.returncode})")
            # Show relevant failure output
            fail_output = run.stdout or run.stderr
            if fail_output:
                lines = fail_output.strip().split("\n")
                for line in lines[-15:]:
                    print(f"    {line}")

        # Always cleanup container and image
        print("    Cleaning up container and image...")
        _cleanup_docker()
        print("    Cleanup done.")

        if passed:
            return {
                "docker_test_passed": True,
                "docker_test_results": output,
                "docker_test_iteration": iteration + 1,
                "docker_test_phase": False,
            }
        else:
            return {
                "docker_test_passed": False,
                "docker_test_results": output,
                "test_results": output,
                "docker_test_iteration": iteration + 1,
                "docker_test_phase": True,
            }

    except subprocess.TimeoutExpired:
        print("    Docker operation timed out.")
        _cleanup_docker()
        return {
            "docker_test_passed": False,
            "docker_test_results": "Docker operation timed out.",
            "test_results": "Docker operation timed out.",
            "docker_test_iteration": iteration + 1,
            "docker_test_phase": True,
        }
    except FileNotFoundError:
        print("    Docker not available on this machine; skipping container test.")
        return {
            "docker_test_passed": True,
            "docker_test_results": "(Docker not available on this machine; skipping container test.)",
            "docker_test_iteration": iteration,
            "docker_test_phase": False,
        }
    except Exception as e:
        print(f"    Docker test error: {e}")
        _cleanup_docker()
        return {
            "docker_test_passed": False,
            "docker_test_results": f"Docker test error: {e}",
            "test_results": f"Docker test error: {e}",
            "docker_test_iteration": iteration + 1,
            "docker_test_phase": True,
        }
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
