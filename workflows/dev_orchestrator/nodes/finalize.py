from __future__ import annotations

from collections.abc import Callable
from typing import Any

from workflows.dev_orchestrator.deps import DevOrchestratorDeps
from workflows.dev_orchestrator.nodes._helpers import advance
from workflows.dev_orchestrator.state import DevOrchestratorState
from workflows.models.enums import WorkflowStatus
from workflows.dev_orchestrator.tools.workspace import Workspace


def make_finalize_node(
    deps: DevOrchestratorDeps,
) -> Callable[[DevOrchestratorState], dict[str, Any]]:
    """Commit the change in the worktree (on success) and record the outcome.

    A run reaches finalize either verified+approved (commit) or exhausted
    (report failure without committing).
    """

    def finalize_node(state: DevOrchestratorState) -> dict[str, Any]:
        report = state.get("verify_report", {})
        gates_ok = bool(report) and all(
            r.get("ok", False) for r in report.values()
        )

        commit_sha: str | None = None
        if gates_ok and state.get("workspace"):
            workspace = Workspace.from_dict(state["workspace"])
            commit_sha = deps.workspace.commit(
                workspace, f"[dev-orchestrator] {state['goal']}"
            )

        return advance(
            state,
            "finalize",
            status=WorkflowStatus.COMPLETED.value if gates_ok else WorkflowStatus.FAILED.value,
            final_result={
                "outcome": "completed" if gates_ok else "failed",
                "commit": commit_sha,
                "iterations": state.get("iteration", 0),
                "verify_report": report,
            },
        )

    return finalize_node
