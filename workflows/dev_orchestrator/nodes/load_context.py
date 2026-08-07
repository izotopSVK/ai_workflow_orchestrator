from __future__ import annotations

from collections.abc import Callable
from typing import Any

from workflows.dev_orchestrator.deps import DevOrchestratorDeps
from workflows.dev_orchestrator.instructions import NoInstructionsProvider
from workflows.dev_orchestrator.mcp_tools import NoMCPToolProvider
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
        mcp = deps.mcp or NoMCPToolProvider()
        root = (state.get("workspace") or {}).get("path", "")

        instructions = provider.load(root) if root else ""
        selected = library.select(root, state["goal"], deps.config.retrieval_k) if root else []
        mcp_tools = mcp.list_tools()

        parts: list[str] = []
        if instructions:
            parts.append(instructions)
        if selected:
            parts.append("# Skills selected for this task")
            for skill in selected:
                parts.append(f"## Skill: {skill.name}\n{skill.body}")
        if mcp_tools:
            parts.append("# Available external tools (via MCP)")
            for t in mcp_tools:
                parts.append(f"- {t.name}: {t.description}")
        agent_instructions = "\n\n".join(parts)

        return advance(
            state,
            "load_context",
            instructions=instructions,
            selected_skills=[{"name": s.name, "description": s.description} for s in selected],
            mcp_tools=[{"name": t.name, "description": t.description, "server": t.server} for t in mcp_tools],
            agent_instructions=agent_instructions,
        )

    return load_context_node
