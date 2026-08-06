from __future__ import annotations

from collections.abc import Callable
from typing import Any

from workflows.dev_orchestrator.deps import DevOrchestratorDeps
from workflows.dev_orchestrator.state import DevOrchestratorState
from workflows.dev_orchestrator.tools.workspace import Workspace


def make_teardown_node(
    deps: DevOrchestratorDeps,
) -> Callable[[DevOrchestratorState], dict[str, Any]]:
    """Release the git worktree once the task is done.

    The commit already lives on the task branch, so removing the worktree is
    safe. Best-effort: teardown failures must not mask the run's outcome.
    """

    def teardown_node(state: DevOrchestratorState) -> dict[str, Any]:
        ws = state.get("workspace")
        if ws:
            try:
                deps.workspace.remove_worktree(Workspace.from_dict(ws))
            except Exception:  # noqa: BLE001 - teardown is best-effort
                pass

        completed = list(state.get("completed_steps", []))
        completed.append("teardown")

        return {"current_node": "teardown", "completed_steps": completed}

    return teardown_node
