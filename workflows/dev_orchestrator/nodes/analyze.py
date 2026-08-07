from __future__ import annotations

from collections.abc import Callable
from typing import Any

from workflows.dev_orchestrator.deps import DevOrchestratorDeps
from workflows.dev_orchestrator.schemas import Lesson
from workflows.dev_orchestrator.state import DevOrchestratorState


def make_analyze_node(
    deps: DevOrchestratorDeps,
) -> Callable[[DevOrchestratorState], dict[str, Any]]:
    """Map the goal onto concrete target files and PHP 8.4 migration risks."""

    def analyze_node(state: DevOrchestratorState) -> dict[str, Any]:
        lessons = [Lesson(**le) for le in state.get("retrieved_lessons", [])]
        analysis = deps.llm.analyze(
            goal=state["goal"],
            lessons=lessons,
            file_hints=state.get("target_files", []),
            system_extra=state.get("agent_instructions", ""),
        )

        completed = list(state.get("completed_steps", []))
        completed.append("analyze")

        return {
            "target_files": analysis.target_files,
            "current_node": "analyze",
            "completed_steps": completed,
        }

    return analyze_node
