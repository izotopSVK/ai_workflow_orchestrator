from __future__ import annotations

from collections.abc import Callable
from typing import Any

from workflows.dev_orchestrator.deps import DevOrchestratorDeps
from workflows.dev_orchestrator.nodes._helpers import advance, context_from_state, record_llm_call
from workflows.dev_orchestrator.schemas import AnalysisOutput
from workflows.dev_orchestrator.state import DevOrchestratorState


def make_plan_node(
    deps: DevOrchestratorDeps,
) -> Callable[[DevOrchestratorState], dict[str, Any]]:
    """Produce an ordered, RAG-informed plan of migration + SOLID steps."""

    def plan_node(state: DevOrchestratorState) -> dict[str, Any]:
        analysis = AnalysisOutput(target_files=state.get("target_files", []))
        plan_output = deps.llm.plan(
            goal=state["goal"],
            analysis=analysis,
            ctx=context_from_state(state),
        )
        return advance(
            state, "plan",
            plan=[step.model_dump() for step in plan_output.steps],
            budget_used=record_llm_call(state),
        )

    return plan_node
