from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Any

from sqlalchemy.orm import Session

from workflows.graph.state import AgentWorkflowState
from workflows.models.enums import ActorType, WorkflowStatus
from workflows.models.schemas import Budget, BudgetUsed
from workflows.persistence.repositories import (
    WorkflowEventRepository,
    WorkflowRepository,
)


class WorkflowNotFound(Exception):
    pass


class WorkflowService:
    """Starts and resumes workflow runs by invoking the LangGraph graph."""

    def __init__(
        self,
        *,
        graph,
        session_factory: Callable[[], Session],
    ):
        self.graph = graph
        self.session_factory = session_factory

    @staticmethod
    def _config(workflow_id: str) -> dict[str, Any]:
        return {"configurable": {"thread_id": workflow_id}}

    def start_workflow(self, *, goal: str) -> dict[str, Any]:
        workflow_id = uuid.uuid4()
        budget = Budget().model_dump()
        budget_used = BudgetUsed().model_dump()

        initial_state: AgentWorkflowState = {
            "workflow_id": str(workflow_id),
            "goal": goal,
            "status": WorkflowStatus.CREATED.value,
            "completed_steps": [],
            "failed_steps": [],
            "artifacts": [],
            "tool_calls": [],
            "errors": [],
            "pending_approval_id": None,
            "budget": budget,
            "budget_used": budget_used,
        }

        with self.session_factory() as session:
            wf_repo = WorkflowRepository(session)
            event_repo = WorkflowEventRepository(session)
            wf_repo.create(
                workflow_id=workflow_id,
                status=WorkflowStatus.CREATED.value,
                budget=budget,
                budget_used=budget_used,
                state=initial_state,
            )
            event_repo.append(
                workflow_id=workflow_id,
                event_type="workflow_created",
                actor_type=ActorType.USER.value,
                payload={"goal": goal},
            )
            session.commit()

        final_state = self.graph.invoke(initial_state, config=self._config(str(workflow_id)))
        self._persist_state(workflow_id, final_state)
        return final_state

    def resume_workflow(
        self,
        workflow_id: str,
        *,
        state_patch: dict[str, Any] | None = None,
        as_node: str | None = None,
    ) -> dict[str, Any]:
        config = self._config(workflow_id)
        if state_patch:
            if as_node is not None:
                self.graph.update_state(config, state_patch, as_node=as_node)
            else:
                self.graph.update_state(config, state_patch)
        final_state = self.graph.invoke(None, config=config)
        self._persist_state(uuid.UUID(workflow_id), final_state)
        return final_state

    def get_state(self, workflow_id: str) -> dict[str, Any] | None:
        snapshot = self.graph.get_state(self._config(workflow_id))
        if snapshot is None or not snapshot.values:
            return None
        return dict(snapshot.values)

    def _persist_state(self, workflow_id: uuid.UUID, state: dict[str, Any]) -> None:
        if not state:
            return
        completed = state.get("status") == WorkflowStatus.COMPLETED.value
        with self.session_factory() as session:
            repo = WorkflowRepository(session)
            repo.update_state(
                workflow_id,
                status=state.get("status"),
                current_node=state.get("current_node"),
                state=state,
                completed=completed,
            )
            session.commit()
