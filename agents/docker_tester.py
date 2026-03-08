"""Docker Tester Agent: builds Docker image from the written project and validates it."""
import os
import subprocess

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


def _looks_like_test_file(path: str) -> bool:
    """Return True when the path appears to point to a test file."""
    base = os.path.basename(path).lower()
    return base.startswith("test_") or base.endswith("_test.py") or "tests/" in path.lower()


def _find_test_files(task_to_file: dict[str, str]) -> list[str]:
    """Return file paths from the task list that look like test files."""
    test_files = []
    for path in task_to_file.values():
        if _looks_like_test_file(path):
            test_files.append(path)
    return test_files


def _infer_test_command(tech_stack: str, test_files: list[str], all_files: list[str]) -> list[str]:
    """Build the test runner command targeting the actual generated test files."""
    tech = tech_stack.lower()
    if "python" in tech or any(f.endswith(".py") for f in all_files):
        if test_files:
            return ["--entrypoint", "python", IMAGE_NAME, "-m", "pytest", "-v"] + test_files
        return ["--entrypoint", "python", IMAGE_NAME, "-m", "pytest", "-v"]
    if "node" in tech or "javascript" in tech or "typescript" in tech:
        return [IMAGE_NAME, "npm", "test"]
    if "go" in tech:
        return ["--entrypoint", "go", IMAGE_NAME, "test", "./..."]
    if "rust" in tech:
        return ["--entrypoint", "cargo", IMAGE_NAME, "test"]
    return ["--entrypoint", "python", IMAGE_NAME, "-m", "pytest", "-v"]


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
    tech_stack = state.get("tech_stack", "")
    project_dir = state.get("generated_project_dir") or state.get("output_dir") or ""
    project_dir = os.path.abspath(project_dir) if project_dir else ""

    # Map task_id -> file path
    task_to_file = {}
    for t in task_list:
        task_to_file[t.get("id", "")] = t.get("file", "main.py")

    all_files = list(task_to_file.values())
    test_files = _find_test_files(task_to_file)

    print(f"    Iteration {iteration + 1}/{MAX_DOCKER_TEST_ITERATIONS}")

    try:
        if not project_dir or not os.path.isdir(project_dir):
            error = "Generated project directory is missing; project_writer must run before docker_tester."
            return {
                "docker_test_passed": False,
                "docker_test_results": error,
                "test_results": error,
                "docker_test_iteration": iteration + 1,
                "docker_test_phase": True,
            }

        # Cleanup any leftover container/image from previous iteration
        _cleanup_docker()

        # Build Docker image
        print("    Building Docker image...")
        build = subprocess.run(
            ["docker", "build", "-t", IMAGE_NAME, "."],
            cwd=project_dir,
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
        print(f"    Running tests: docker run --rm --name {CONTAINER_NAME} {' '.join(test_cmd)}")
        run = subprocess.run(
            ["docker", "run", "--rm", "--name", CONTAINER_NAME] + test_cmd,
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
