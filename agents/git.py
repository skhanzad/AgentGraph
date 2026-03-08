"""Git Agent: initialize and snapshot the generated project in a git repository."""
from __future__ import annotations

import os
import subprocess

from state import SoftwareAgentState


def _run_git(args: list[str], cwd: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git"] + args,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=60,
    )


def git_node(state: SoftwareAgentState) -> SoftwareAgentState:
    project_dir = state.get("generated_project_dir") or state.get("output_dir") or ""
    project_dir = os.path.abspath(project_dir) if project_dir else ""
    if not project_dir or not os.path.isdir(project_dir):
        return {
            "git_initialized": False,
            "git_commit_hash": "",
            "git_status": "Project directory is missing; project_writer must run before git_node.",
        }

    try:
        current_task_index = state.get("current_task_index", 0)
        test_iteration = state.get("test_iteration", 0)
        orchestration_phase = state.get("orchestration_phase", "")
        init = _run_git(["init"], project_dir)
        if init.returncode != 0:
            return {
                "git_initialized": False,
                "git_commit_hash": "",
                "git_status": init.stderr.strip() or init.stdout.strip() or "git init failed",
            }

        _run_git(["config", "user.name", "AgentGraph"], project_dir)
        _run_git(["config", "user.email", "agentgraph@example.local"], project_dir)

        add = _run_git(["add", "."], project_dir)
        if add.returncode != 0:
            return {
                "git_initialized": True,
                "git_commit_hash": "",
                "git_status": add.stderr.strip() or add.stdout.strip() or "git add failed",
            }

        if orchestration_phase == "release_parallel":
            commit_message = "Release snapshot"
        else:
            commit_message = f"Code snapshot task-{current_task_index}-test-{test_iteration}"
        commit = _run_git(["commit", "-m", commit_message], project_dir)
        if commit.returncode != 0:
            # If there is nothing new to commit, still treat repo init as successful.
            if "nothing to commit" not in commit.stdout.lower() and "nothing to commit" not in commit.stderr.lower():
                return {
                    "git_initialized": True,
                    "git_commit_hash": "",
                    "git_status": commit.stderr.strip() or commit.stdout.strip() or "git commit failed",
                }

        rev_parse = _run_git(["rev-parse", "HEAD"], project_dir)
        commit_hash = rev_parse.stdout.strip() if rev_parse.returncode == 0 else ""
        status = _run_git(["status", "--short"], project_dir)
        git_status = status.stdout.strip()

        return {
            "git_initialized": True,
            "git_commit_hash": commit_hash,
            "git_status": git_status,
        }
    except FileNotFoundError:
        return {
            "git_initialized": False,
            "git_commit_hash": "",
            "git_status": "git is not installed or not available on PATH.",
        }
    except Exception as exc:
        return {
            "git_initialized": False,
            "git_commit_hash": "",
            "git_status": f"git node error: {exc}",
        }
