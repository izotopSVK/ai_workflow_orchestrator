import uuid
from typing import Any

from sqlalchemy.orm import Session

from workflows.models.enums import ActorType, ApprovalStatus
from workflows.persistence.orm import HumanApproval
from workflows.persistence.repositories import (
    HumanApprovalRepository,
    WorkflowEventRepository,
)


class ApprovalNotFound(Exception):
    pass


class ApprovalAlreadyDecided(Exception):
    pass


class ApprovalService:
    def __init__(self, session: Session):
        self.session = session
        self.repo = HumanApprovalRepository(session)
        self.events = WorkflowEventRepository(session)

    def get(self, approval_id: uuid.UUID) -> HumanApproval:
        approval = self.repo.get(approval_id)
        if approval is None:
            raise ApprovalNotFound(str(approval_id))
        return approval

    def approve(
        self,
        approval_id: uuid.UUID,
        *,
        decided_by: str | None = None,
        decision: dict[str, Any] | None = None,
    ) -> HumanApproval:
        return self._decide(
            approval_id,
            new_status=ApprovalStatus.APPROVED,
            decided_by=decided_by,
            decision=decision,
            event_type="approval_granted",
        )

    def reject(
        self,
        approval_id: uuid.UUID,
        *,
        decided_by: str | None = None,
        decision: dict[str, Any] | None = None,
    ) -> HumanApproval:
        return self._decide(
            approval_id,
            new_status=ApprovalStatus.REJECTED,
            decided_by=decided_by,
            decision=decision,
            event_type="approval_rejected",
        )

    def _decide(
        self,
        approval_id: uuid.UUID,
        *,
        new_status: ApprovalStatus,
        decided_by: str | None,
        decision: dict[str, Any] | None,
        event_type: str,
    ) -> HumanApproval:
        existing = self.repo.get(approval_id)
        if existing is None:
            raise ApprovalNotFound(str(approval_id))
        if existing.status != ApprovalStatus.PENDING.value:
            raise ApprovalAlreadyDecided(
                f"Approval {approval_id} already in status {existing.status}"
            )
        updated = self.repo.decide(
            approval_id,
            status=new_status.value,
            decided_by=decided_by,
            decision=decision,
        )
        assert updated is not None
        self.events.append(
            workflow_id=updated.workflow_id,
            event_type=event_type,
            actor_type=ActorType.USER.value,
            actor_id=decided_by,
            payload={"approval_id": str(updated.id)},
        )
        return updated
