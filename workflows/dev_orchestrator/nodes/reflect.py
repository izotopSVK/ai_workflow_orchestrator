from __future__ import annotations

from collections.abc import Callable
from typing import Any

from workflows.dev_orchestrator.deps import DevOrchestratorDeps
from workflows.dev_orchestrator.nodes._helpers import advance, context_from_state
from workflows.dev_orchestrator.state import DevOrchestratorState
from workflows.models.enums import WorkflowStatus


def make_reflect_node(
    deps: DevOrchestratorDeps,
) -> Callable[[DevOrchestratorState], dict[str, Any]]:
    """Reflexion: turn a failed verify into a lesson and prime the retry.

    The lesson is both threaded into the next implement pass (via state) and
    persisted to memory so future *runs* benefit, not just this iteration. Sets
    status back to RUNNING so the loop can continue.
    """

    def reflect_node(state: DevOrchestratorState) -> dict[str, Any]:
        lesson = deps.llm.reflect(
            goal=state["goal"],
            verify_report=state.get("verify_report", {}),
            ctx=context_from_state(state),
        )
        lesson_id = deps.memory.record_lesson(lesson)
        lesson.id = lesson_id

        reflections = list(state.get("reflections", []))
        reflections.append(lesson.model_dump())

        return advance(
            state,
            "reflect",
            reflections=reflections,
            status=WorkflowStatus.RUNNING.value,
        )

    return reflect_node
