"""Shared helpers for graph nodes to keep each node focused on its own logic."""

from __future__ import annotations

from typing import Any

from workflows.dev_orchestrator.schemas import Lesson, PromptContext
from workflows.dev_orchestrator.state import DevOrchestratorState


def advance(state: DevOrchestratorState, node: str, **updates: Any) -> dict[str, Any]:
    """Standard node return: append ``node`` to completed_steps and set current_node.

    Replaces the copy-pasted ``completed = list(...); completed.append(...)``
    boilerplate that every node used to carry.
    """
    completed = list(state.get("completed_steps", []))
    completed.append(node)
    return {"current_node": node, "completed_steps": completed, **updates}


def record_llm_call(state: DevOrchestratorState, n: int = 1) -> dict[str, Any]:
    """Return budget_used with the LLM-call counter incremented by ``n``."""
    used = dict(state.get("budget_used", {}))
    used["llm_calls"] = used.get("llm_calls", 0) + n
    return used


def context_from_state(state: DevOrchestratorState) -> PromptContext:
    """Assemble the per-run PromptContext (lessons + reflections + instructions)."""
    return PromptContext(
        lessons=[Lesson(**le) for le in state.get("retrieved_lessons", [])],
        reflections=[r.get("detail", "") for r in state.get("reflections", [])],
        instructions=state.get("agent_instructions", ""),
    )
