from __future__ import annotations

from collections.abc import Callable
from typing import Any

from workflows.dev_orchestrator.deps import DevOrchestratorDeps
from workflows.dev_orchestrator.schemas import AnalysisOutput, Lesson
from workflows.dev_orchestrator.state import DevOrchestratorState


def make_plan_node(
    deps: DevOrchestratorDeps,
) -> Callable[[DevOrchestratorState], dict[str, Any]]:
    """Produce an ordered, RAG-informed plan of migration + SOLID steps."""

    def plan_node(state: DevOrchestratorState) -> dict[str, Any]:
        lessons = [Lesson(**le) for le in state.get("retrieved_lessons", [])]
        analysis = AnalysisOutput(target_files=state.get("target_files", []))
        plan_output = deps.llm.plan(
            goal=state["goal"],
            analysis=analysis,
            lessons=lessons,
            system_extra=state.get("agent_instructions", ""),
        )

        completed = list(state.get("completed_steps", []))
        completed.append("plan")

        return {
            "plan": [step.model_dump() for step in plan_output.steps],
            "current_node": "plan",
            "completed_steps": completed,
        }

    return plan_node
