import uuid
from typing import Any

from sqlalchemy.orm import Session

from workflows.persistence.repositories import WorkflowEventRepository


class EventService:
    def __init__(self, session: Session):
        self.session = session
        self.repo = WorkflowEventRepository(session)

    def append(
        self,
        *,
        workflow_id: uuid.UUID,
        event_type: str,
        actor_type: str,
        actor_id: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> None:
        self.repo.append(
            workflow_id=workflow_id,
            event_type=event_type,
            actor_type=actor_type,
            actor_id=actor_id,
            payload=payload,
        )

    def list(self, workflow_id: uuid.UUID) -> list[dict[str, Any]]:
        events = self.repo.list_for_workflow(workflow_id)
        return [
            {
                "id": str(e.id),
                "event_type": e.event_type,
                "actor_type": e.actor_type,
                "actor_id": e.actor_id,
                "payload": e.payload_json,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in events
        ]
