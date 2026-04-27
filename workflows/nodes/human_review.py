import uuid
from collections.abc import Callable
from typing import Any

from workflows.graph.deps import WorkflowDeps
from workflows.graph.state import AgentWorkflowState
from workflows.models.enums import (
    ActorType,
    ApprovalStatus,
    ApprovalType,
    WorkflowStatus,
)
from workflows.persistence.repositories import (
    HumanApprovalRepository,
    WorkflowEventRepository,
)


def make_human_review_node(
    deps: WorkflowDeps,
) -> Callable[[AgentWorkflowState], dict[str, Any]]:
    def human_review_node(state: AgentWorkflowState) -> dict[str, Any]:
        if state.get("pending_approval_id"):
            return {
                "current_node": "human_review",
                "status": WorkflowStatus.WAITING_FOR_HUMAN.value,
            }

        workflow_id = uuid.UUID(state["workflow_id"])
        with deps.session_factory() as session:
            approval_repo = HumanApprovalRepository(session)
            event_repo = WorkflowEventRepository(session)

            approval = approval_repo.create(
                workflow_id=workflow_id,
                approval_type=ApprovalType.FINAL_REPORT_APPROVAL.value,
                status=ApprovalStatus.PENDING.value,
                payload={
                    "goal": state["goal"],
                    "plan": state.get("plan", []),
                },
                requested_by="workflow",
            )
            event_repo.append(
                workflow_id=workflow_id,
                event_type="approval_requested",
                actor_type=ActorType.SYSTEM.value,
                payload={"approval_id": str(approval.id)},
            )
            session.commit()
            approval_id = str(approval.id)

        return {
            "current_node": "human_review",
            "status": WorkflowStatus.WAITING_FOR_HUMAN.value,
            "pending_approval_id": approval_id,
        }

    return human_review_node
