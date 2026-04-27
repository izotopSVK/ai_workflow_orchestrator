from collections.abc import Callable
from typing import Any

from workflows.graph.deps import WorkflowDeps
from workflows.graph.state import AgentWorkflowState
from workflows.models.enums import WorkflowStatus


def make_plan_node(deps: WorkflowDeps) -> Callable[[AgentWorkflowState], dict[str, Any]]:
    def plan_node(state: AgentWorkflowState) -> dict[str, Any]:
        plan_output = deps.llm.generate_plan(state["goal"])

        completed = list(state.get("completed_steps", []))
        completed.append("plan")

        budget_used = dict(state.get("budget_used", {}))
        budget_used["llm_calls"] = budget_used.get("llm_calls", 0) + 1

        return {
            "plan": [item.model_dump() for item in plan_output.steps],
            "completed_steps": completed,
            "current_node": "plan",
            "status": WorkflowStatus.RUNNING.value,
            "budget_used": budget_used,
        }

    return plan_node
