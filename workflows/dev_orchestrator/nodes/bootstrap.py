from __future__ import annotations

from collections.abc import Callable
from typing import Any

from workflows.dev_orchestrator.deps import DevOrchestratorDeps
from workflows.dev_orchestrator.state import DevOrchestratorState
from workflows.models.enums import WorkflowStatus


def make_bootstrap_node(
    deps: DevOrchestratorDeps,
) -> Callable[[DevOrchestratorState], dict[str, Any]]:
    """Provision the isolated workspace before any development starts.

    git worktree add -> copy per-task config files -> symlink heavy shared dirs.
    All deterministic and side-effecting, so it lives in a tool, not the LLM.
    """

    def bootstrap_node(state: DevOrchestratorState) -> dict[str, Any]:
        cfg = deps.config
        short_id = state["workflow_id"].split("-")[0][:8]
        branch = f"{cfg.branch_prefix}{short_id}"

        workspace = deps.workspace.create_worktree(base_ref=cfg.base_ref, branch=branch)
        deps.workspace.copy_files(workspace, cfg.copy_globs)
        deps.workspace.link_files(workspace, cfg.symlink_map)

        completed = list(state.get("completed_steps", []))
        completed.append("bootstrap")

        return {
            "workspace": workspace.as_dict(),
            "current_node": "bootstrap",
            "status": WorkflowStatus.RUNNING.value,
            "completed_steps": completed,
        }

    return bootstrap_node
