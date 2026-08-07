from __future__ import annotations

from collections.abc import Callable
from typing import Any

from workflows.dev_orchestrator.deps import DevOrchestratorDeps
from workflows.dev_orchestrator.instructions import NoInstructionsProvider
from workflows.dev_orchestrator.nodes._helpers import advance
from workflows.dev_orchestrator.skills import EmptySkillLibrary
from workflows.dev_orchestrator.state import DevOrchestratorState


def make_load_context_node(
    deps: DevOrchestratorDeps,
) -> Callable[[DevOrchestratorState], dict[str, Any]]:
    """Load AGENTS.md-style instructions + relevant skills from the worktree.

    Runs after bootstrap (the worktree exists) and composes ``agent_instructions``
    — the project instructions plus the task-relevant skill bodies — which every
    agent's system prompt is extended with for the rest of the run.
    """

    def load_context_node(state: DevOrchestratorState) -> dict[str, Any]:
        provider = deps.instructions or NoInstructionsProvider()
        library = deps.skills or EmptySkillLibrary()
        root = (state.get("workspace") or {}).get("path", "")

        instructions = provider.load(root) if root else ""
        selected = library.select(root, state["goal"], deps.config.retrieval_k) if root else []

        parts: list[str] = []
        if instructions:
            parts.append(instructions)
        if selected:
            parts.append("# Skills selected for this task")
            for skill in selected:
                parts.append(f"## Skill: {skill.name}\n{skill.body}")
        agent_instructions = "\n\n".join(parts)

        return advance(
            state,
            "load_context",
            instructions=instructions,
            selected_skills=[{"name": s.name, "description": s.description} for s in selected],
            agent_instructions=agent_instructions,
        )

    return load_context_node
