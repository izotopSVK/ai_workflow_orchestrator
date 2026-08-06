from __future__ import annotations

from collections.abc import Callable
from typing import Any

from workflows.dev_orchestrator.deps import DevOrchestratorDeps
from workflows.dev_orchestrator.schemas import Lesson, PlanOutput, PlanStep
from workflows.dev_orchestrator.state import DevOrchestratorState


def make_implement_node(
    deps: DevOrchestratorDeps,
) -> Callable[[DevOrchestratorState], dict[str, Any]]:
    """Generate the code change as a diff.

    On the Reflexion retry path, prior reflections are fed back in so the LLM
    corrects the specific failure rather than regenerating blindly. Bumps the
    iteration counter that bounds the loop.
    """

    def implement_node(state: DevOrchestratorState) -> dict[str, Any]:
        lessons = [Lesson(**le) for le in state.get("retrieved_lessons", [])]
        plan = PlanOutput(steps=[PlanStep(**s) for s in state.get("plan", [])])
        reflections = [r.get("detail", "") for r in state.get("reflections", [])]

        result = deps.llm.implement(
            goal=state["goal"],
            plan=plan,
            reflections=reflections,
            lessons=lessons,
        )

        completed = list(state.get("completed_steps", []))
        completed.append("implement")

        return {
            "diff": result.diff,
            "target_files": result.touched_files or state.get("target_files", []),
            "iteration": state.get("iteration", 0) + 1,
            "current_node": "implement",
            "completed_steps": completed,
        }

    return implement_node
