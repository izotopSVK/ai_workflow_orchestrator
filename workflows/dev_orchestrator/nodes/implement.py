from __future__ import annotations

from collections.abc import Callable
from typing import Any

from workflows.dev_orchestrator.deps import DevOrchestratorDeps
from workflows.dev_orchestrator.mcp_tools import NoMCPToolProvider
from workflows.dev_orchestrator.nodes._helpers import advance, context_from_state
from workflows.dev_orchestrator.schemas import PlanOutput, PlanStep
from workflows.dev_orchestrator.state import DevOrchestratorState


def make_implement_node(
    deps: DevOrchestratorDeps,
) -> Callable[[DevOrchestratorState], dict[str, Any]]:
    """Generate the code change as a diff.

    On the Reflexion retry path, prior reflections (carried in the PromptContext)
    are fed back so the LLM corrects the specific failure. When MCP tools are
    available they are offered to the agent's function-calling loop. Bumps the
    iteration counter that bounds the Reflexion loop.
    """

    def implement_node(state: DevOrchestratorState) -> dict[str, Any]:
        plan = PlanOutput(steps=[PlanStep(**s) for s in state.get("plan", [])])
        mcp = deps.mcp or NoMCPToolProvider()
        tools = mcp.list_tools()
        result = deps.llm.implement(
            goal=state["goal"],
            plan=plan,
            ctx=context_from_state(state),
            tools=tools or None,
            execute=mcp.call_tool if tools else None,
        )
        return advance(
            state,
            "implement",
            diff=result.diff,
            target_files=result.touched_files or state.get("target_files", []),
            iteration=state.get("iteration", 0) + 1,
        )

    return implement_node
