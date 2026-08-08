from __future__ import annotations

import time
import uuid
from typing import Any

from workflows.dev_orchestrator.config import DevOrchestratorConfig
from workflows.dev_orchestrator.state import DevOrchestratorState
from workflows.models.enums import WorkflowStatus


class DevOrchestratorService:
    """Starts and resumes dev-orchestrator runs over the compiled graph.

    Durable resume relies on the LangGraph checkpointer keyed by ``thread_id``,
    exactly like the MVP ``WorkflowService``.
    """

    def __init__(self, *, graph, config: DevOrchestratorConfig):
        self.graph = graph
        self.config = config

    @staticmethod
    def _config(workflow_id: str) -> dict[str, Any]:
        return {"configurable": {"thread_id": workflow_id}}

    def start(self, *, goal: str, workflow_id: str | None = None) -> dict[str, Any]:
        workflow_id = workflow_id or str(uuid.uuid4())
        initial_state: DevOrchestratorState = {
            "workflow_id": workflow_id,
            "goal": goal,
            "status": WorkflowStatus.CREATED.value,
            "retrieved_lessons": [],
            "target_files": [],
            "iteration": 0,
            "max_iterations": self.config.max_iterations,
            "reflections": [],
            "completed_steps": [],
            "errors": [],
            "pending_approval_id": None,
            "max_llm_calls": self.config.max_llm_calls,
            "max_runtime_seconds": self.config.max_runtime_seconds,
            "started_at": time.time(),
            "budget_used": {"llm_calls": 0},
        }
        return self.graph.invoke(initial_state, config=self._config(workflow_id))

    def approve(self, workflow_id: str) -> dict[str, Any]:
        """Resume a run parked at human_review after approval."""
        config = self._config(workflow_id)
        self.graph.update_state(
            config,
            {"status": WorkflowStatus.RUNNING.value, "pending_approval_id": None},
            as_node="human_review",
        )
        return self.graph.invoke(None, config=config)

    def get_state(self, workflow_id: str) -> dict[str, Any] | None:
        snapshot = self.graph.get_state(self._config(workflow_id))
        if snapshot is None or not snapshot.values:
            return None
        return dict(snapshot.values)
