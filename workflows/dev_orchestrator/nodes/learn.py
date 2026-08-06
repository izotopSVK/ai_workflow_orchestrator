from __future__ import annotations

from collections.abc import Callable
from typing import Any

from workflows.dev_orchestrator.deps import DevOrchestratorDeps
from workflows.dev_orchestrator.schemas import Episode
from workflows.dev_orchestrator.state import DevOrchestratorState


def make_learn_node(
    deps: DevOrchestratorDeps,
) -> Callable[[DevOrchestratorState], dict[str, Any]]:
    """Close the self-learning loop: persist the episode and reward lessons.

    On success, every lesson that was applied this run gets a positive reward,
    so genuinely helpful lessons rank higher in future retrievals.
    """

    def learn_node(state: DevOrchestratorState) -> dict[str, Any]:
        final = state.get("final_result", {})
        outcome = final.get("outcome", "failed")

        episode = Episode(
            workflow_id=state["workflow_id"],
            goal=state["goal"],
            outcome=outcome,
            iterations=state.get("iteration", 0),
            target_files=state.get("target_files", []),
            summary=f"{outcome} in {state.get('iteration', 0)} iteration(s)",
        )
        deps.memory.record_episode(episode)

        if outcome == "completed":
            for reflection in state.get("reflections", []):
                lesson_id = reflection.get("id")
                if lesson_id:
                    deps.memory.reinforce(lesson_id, reward=1.0)

        completed = list(state.get("completed_steps", []))
        completed.append("learn")

        return {"current_node": "learn", "completed_steps": completed}

    return learn_node
