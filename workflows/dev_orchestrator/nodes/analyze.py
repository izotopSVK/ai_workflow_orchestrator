from __future__ import annotations

from collections.abc import Callable
from typing import Any

from workflows.dev_orchestrator.deps import DevOrchestratorDeps
from workflows.dev_orchestrator.mcp_tools import NoMCPToolProvider
from workflows.dev_orchestrator.nodes._helpers import advance, context_from_state
from workflows.dev_orchestrator.state import DevOrchestratorState


def make_analyze_node(
    deps: DevOrchestratorDeps,
) -> Callable[[DevOrchestratorState], dict[str, Any]]:
    """Map the goal onto concrete target files and PHP 8.4 migration risks.

    When MCP tools are available they are offered to the agent's function-calling
    loop (e.g. to read files or inspect git history before deciding).
    """

    def analyze_node(state: DevOrchestratorState) -> dict[str, Any]:
        mcp = deps.mcp or NoMCPToolProvider()
        tools = mcp.list_tools()
        analysis = deps.llm.analyze(
            goal=state["goal"],
            file_hints=state.get("target_files", []),
            ctx=context_from_state(state),
            tools=tools or None,
            execute=mcp.call_tool if tools else None,
        )
        return advance(state, "analyze", target_files=analysis.target_files)

    return analyze_node
