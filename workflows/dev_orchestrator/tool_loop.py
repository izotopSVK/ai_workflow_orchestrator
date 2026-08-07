"""Function-calling loop: let a chat model call MCP tools before answering.

The model is bound with the available MCP tools; while it emits tool calls we
execute them (via the MCP provider) and feed the results back, until it stops
calling tools or the step budget is exhausted. The caller then coerces the
enriched conversation into a structured result.

The loop is a pure, transport-agnostic function: it takes any object with an
``invoke(messages) -> AIMessage`` method and an ``execute(name, args)`` callable,
so it is fully unit-testable with a fake chat and no network. Only
``langchain_core`` messages are used (always installed); ``langchain-openai`` is
not required here.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from langchain_core.messages import ToolMessage

from workflows.dev_orchestrator.mcp_tools import MCPToolResult, MCPToolSpec


@dataclass
class ToolCallRecord:
    name: str
    args: dict[str, Any]
    ok: bool
    content: str


@dataclass
class ToolLoopResult:
    messages: list[Any]
    steps: list[ToolCallRecord] = field(default_factory=list)


def mcp_specs_to_openai_tools(specs: list[MCPToolSpec]) -> list[dict]:
    """Render MCP tool specs as OpenAI/Copilot function-tool schemas for bind_tools."""
    tools: list[dict] = []
    for spec in specs:
        schema = spec.input_schema
        if not (isinstance(schema, dict) and schema.get("type") == "object"):
            schema = {"type": "object", "properties": {}, "additionalProperties": True}
        tools.append({
            "type": "function",
            "function": {
                "name": spec.name,
                "description": spec.description or "",
                "parameters": schema,
            },
        })
    return tools


def run_tool_loop(
    chat: Any,
    messages: list[Any],
    execute: Callable[[str, dict[str, Any]], MCPToolResult],
    *,
    max_steps: int = 6,
) -> ToolLoopResult:
    """Drive ``chat`` through tool calls until it answers without calling a tool.

    ``chat`` must already be bound with the tools (``bind_tools``). Returns the
    full conversation (including the assistant/tool turns) plus a record of each
    executed tool call.
    """
    convo = list(messages)
    steps: list[ToolCallRecord] = []

    for _ in range(max_steps):
        ai = chat.invoke(convo)
        convo.append(ai)
        tool_calls = getattr(ai, "tool_calls", None) or []
        if not tool_calls:
            break
        for call in tool_calls:
            name = call["name"]
            args = call.get("args", {}) or {}
            call_id = call.get("id") or name
            result = execute(name, args)
            content = result.content if result.ok else f"ERROR: {result.error}"
            steps.append(ToolCallRecord(name=name, args=args, ok=result.ok, content=content))
            convo.append(ToolMessage(content=content, tool_call_id=call_id))

    return ToolLoopResult(messages=convo, steps=steps)
