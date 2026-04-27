from collections.abc import Callable
from typing import Any

from workflows.graph.deps import WorkflowDeps
from workflows.graph.state import AgentWorkflowState
from workflows.models.enums import WorkflowStatus


def make_verify_node(deps: WorkflowDeps) -> Callable[[AgentWorkflowState], dict[str, Any]]:
    def verify_node(state: AgentWorkflowState) -> dict[str, Any]:
        plan = state.get("plan") or []
        errors: list[dict[str, Any]] = list(state.get("errors", []))

        if not plan:
            errors.append({"node": "verify", "message": "Plan is empty"})

        completed = list(state.get("completed_steps", []))

        if errors:
            return {
                "errors": errors,
                "status": WorkflowStatus.FAILED.value,
                "current_node": "verify",
            }

        completed.append("verify")
        return {
            "completed_steps": completed,
            "current_node": "verify",
            "status": WorkflowStatus.RUNNING.value,
        }

    return verify_node
