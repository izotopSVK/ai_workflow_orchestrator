from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Any

from workflows.dev_orchestrator.deps import DevOrchestratorDeps
from workflows.dev_orchestrator.state import DevOrchestratorState
from workflows.models.enums import WorkflowStatus


def make_human_review_node(
    deps: DevOrchestratorDeps,
) -> Callable[[DevOrchestratorState], dict[str, Any]]:
    """Pause for human approval of the verified diff before it is committed.

    Mirrors the MVP graph's interrupt pattern: the node sets WAITING_FOR_HUMAN
    and the router sends the graph to END; a resume with a cleared
    ``pending_approval_id`` continues to finalize. Persistence of the approval
    record is intentionally left to the integration layer in the scaffold.
    """

    def human_review_node(state: DevOrchestratorState) -> dict[str, Any]:
        if not deps.config.require_human_review:
            return {"current_node": "human_review", "status": WorkflowStatus.RUNNING.value}

        if state.get("pending_approval_id"):
            # Already requested; stay parked until resumed.
            return {
                "current_node": "human_review",
                "status": WorkflowStatus.WAITING_FOR_HUMAN.value,
            }

        completed = list(state.get("completed_steps", []))
        completed.append("human_review")

        return {
            "current_node": "human_review",
            "status": WorkflowStatus.WAITING_FOR_HUMAN.value,
            "pending_approval_id": str(uuid.uuid4()),
            "completed_steps": completed,
        }

    return human_review_node
