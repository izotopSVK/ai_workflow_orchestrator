from __future__ import annotations

from collections.abc import Callable
from typing import Any

from workflows.dev_orchestrator.deps import DevOrchestratorDeps
from workflows.dev_orchestrator.state import DevOrchestratorState


def make_retrieve_node(
    deps: DevOrchestratorDeps,
) -> Callable[[DevOrchestratorState], dict[str, Any]]:
    """Self-learning entry point: pull relevant lessons from long-term memory.

    Retrieved lessons are threaded into analyze/plan/implement prompts so the
    orchestrator stops repeating mistakes it has already learned from.
    """

    def retrieve_node(state: DevOrchestratorState) -> dict[str, Any]:
        lessons = deps.memory.retrieve_lessons(state["goal"], deps.config.retrieval_k)

        completed = list(state.get("completed_steps", []))
        completed.append("retrieve")

        return {
            "retrieved_lessons": [le.model_dump() for le in lessons],
            "current_node": "retrieve",
            "completed_steps": completed,
        }

    return retrieve_node
