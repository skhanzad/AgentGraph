"""Project writer node: materialize the current project/state to disk."""
from __future__ import annotations

import os

from config import OUTPUT_DIR
from project_writer import write_project, write_state_snapshot
from state import SoftwareAgentState


def project_writer_node(state: SoftwareAgentState) -> SoftwareAgentState:
    out_dir = os.path.abspath(state.get("output_dir") or OUTPUT_DIR)
    write_project(state, out_dir)
    snapshot_path = write_state_snapshot(state, out_dir)
    return {
        "generated_project_dir": out_dir,
        "state_snapshot_path": snapshot_path,
    }
