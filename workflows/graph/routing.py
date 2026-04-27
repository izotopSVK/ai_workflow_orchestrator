from workflows.graph.state import AgentWorkflowState
from workflows.models.enums import WorkflowStatus


def route_after_verify(state: AgentWorkflowState) -> str:
    if state.get("status") == WorkflowStatus.FAILED.value or state.get("errors"):
        return "end"
    return "human_review"


def route_after_human_review(state: AgentWorkflowState) -> str:
    status = state.get("status")
    if status == WorkflowStatus.WAITING_FOR_HUMAN.value:
        return "end"
    if status == WorkflowStatus.RUNNING.value:
        return "finalize"
    return "end"
