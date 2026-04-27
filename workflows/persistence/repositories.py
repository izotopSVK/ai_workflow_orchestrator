import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from workflows.persistence.orm import (
    HumanApproval,
    Workflow,
    WorkflowArtifact,
    WorkflowEvent,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class WorkflowRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(
        self,
        *,
        workflow_id: uuid.UUID,
        status: str,
        budget: dict[str, Any],
        budget_used: dict[str, Any],
        state: dict[str, Any],
    ) -> Workflow:
        workflow = Workflow(
            id=workflow_id,
            status=status,
            state_json=state,
            budget_json=budget,
            budget_used_json=budget_used,
        )
        self.session.add(workflow)
        self.session.flush()
        return workflow

    def get(self, workflow_id: uuid.UUID) -> Workflow | None:
        return self.session.get(Workflow, workflow_id)

    def update_state(
        self,
        workflow_id: uuid.UUID,
        *,
        status: str | None = None,
        current_node: str | None = None,
        state: dict[str, Any] | None = None,
        completed: bool = False,
    ) -> Workflow | None:
        workflow = self.session.get(Workflow, workflow_id)
        if workflow is None:
            return None
        if status is not None:
            workflow.status = status
        if current_node is not None:
            workflow.current_node = current_node
        if state is not None:
            workflow.state_json = state
        if completed:
            workflow.completed_at = _utcnow()
        self.session.flush()
        return workflow


class HumanApprovalRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(
        self,
        *,
        workflow_id: uuid.UUID,
        approval_type: str,
        status: str,
        payload: dict[str, Any],
        requested_by: str | None = None,
    ) -> HumanApproval:
        approval = HumanApproval(
            workflow_id=workflow_id,
            approval_type=approval_type,
            status=status,
            payload_json=payload,
            requested_by=requested_by,
        )
        self.session.add(approval)
        self.session.flush()
        return approval

    def get(self, approval_id: uuid.UUID) -> HumanApproval | None:
        return self.session.get(HumanApproval, approval_id)

    def decide(
        self,
        approval_id: uuid.UUID,
        *,
        status: str,
        decided_by: str | None,
        decision: dict[str, Any] | None,
    ) -> HumanApproval | None:
        approval = self.session.get(HumanApproval, approval_id)
        if approval is None:
            return None
        approval.status = status
        approval.decided_by = decided_by
        approval.decision_json = decision
        approval.decided_at = _utcnow()
        self.session.flush()
        return approval


class WorkflowEventRepository:
    def __init__(self, session: Session):
        self.session = session

    def append(
        self,
        *,
        workflow_id: uuid.UUID,
        event_type: str,
        actor_type: str,
        actor_id: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> WorkflowEvent:
        event = WorkflowEvent(
            workflow_id=workflow_id,
            event_type=event_type,
            actor_type=actor_type,
            actor_id=actor_id,
            payload_json=payload or {},
        )
        self.session.add(event)
        self.session.flush()
        return event

    def list_for_workflow(self, workflow_id: uuid.UUID) -> list[WorkflowEvent]:
        stmt = (
            select(WorkflowEvent)
            .where(WorkflowEvent.workflow_id == workflow_id)
            .order_by(WorkflowEvent.created_at)
        )
        return list(self.session.scalars(stmt))


class WorkflowArtifactRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(
        self,
        *,
        workflow_id: uuid.UUID,
        artifact_type: str,
        uri: str,
        mime_type: str | None = None,
        size_bytes: int | None = None,
        checksum: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> WorkflowArtifact:
        artifact = WorkflowArtifact(
            workflow_id=workflow_id,
            artifact_type=artifact_type,
            uri=uri,
            mime_type=mime_type,
            size_bytes=size_bytes,
            checksum=checksum,
            metadata_json=metadata or {},
        )
        self.session.add(artifact)
        self.session.flush()
        return artifact
