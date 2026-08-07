"""MCP (Model Context Protocol) client: expose external MCP-server tools to agents.

Lets the dev orchestrator discover and invoke tools served by external MCP
servers (filesystem, git, docs, DB introspection, …). Same DI shape as the rest
of the codebase: a ``MCPToolProvider`` Protocol with a zero-dependency
:class:`NoMCPToolProvider` default, a scriptable :class:`FakeMCPToolProvider` for
tests, and a :class:`MultiServerMCPToolProvider` backed by
``langchain-mcp-adapters`` for real servers.

The provider is sync (like the rest of the package); the real implementation
wraps the async MCP client internally. ``langchain_mcp_adapters`` is imported
lazily so tests and the default path never require it.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class MCPToolSpec:
    """A tool advertised by an MCP server."""

    name: str
    description: str = ""
    input_schema: dict[str, Any] = field(default_factory=dict)
    server: str = ""


@dataclass
class MCPToolResult:
    """Uniform result of invoking an MCP tool."""

    name: str
    ok: bool
    content: str = ""
    error: str = ""


class MCPToolProvider(Protocol):
    def list_tools(self) -> list[MCPToolSpec]: ...

    def call_tool(self, name: str, arguments: dict[str, Any]) -> MCPToolResult: ...


class NoMCPToolProvider:
    """No MCP servers configured. The default."""

    def list_tools(self) -> list[MCPToolSpec]:
        return []

    def call_tool(self, name: str, arguments: dict[str, Any]) -> MCPToolResult:
        return MCPToolResult(name=name, ok=False, error="No MCP provider configured")


class FakeMCPToolProvider:
    """In-memory MCP provider for tests: register (spec, handler) pairs."""

    def __init__(self, tools: list[tuple[MCPToolSpec, Callable[[dict[str, Any]], str]]] | None = None):
        self._handlers: dict[str, Callable[[dict[str, Any]], str]] = {}
        self._specs: dict[str, MCPToolSpec] = {}
        for spec, handler in tools or []:
            self._specs[spec.name] = spec
            self._handlers[spec.name] = handler
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def list_tools(self) -> list[MCPToolSpec]:
        return list(self._specs.values())

    def call_tool(self, name: str, arguments: dict[str, Any]) -> MCPToolResult:
        self.calls.append((name, arguments))
        handler = self._handlers.get(name)
        if handler is None:
            return MCPToolResult(name=name, ok=False, error="unknown tool")
        try:
            return MCPToolResult(name=name, ok=True, content=handler(arguments))
        except Exception as exc:  # noqa: BLE001 - surface tool errors uniformly
            return MCPToolResult(name=name, ok=False, error=str(exc))


class MultiServerMCPToolProvider:
    """Real provider backed by ``langchain-mcp-adapters`` (MultiServerMCPClient).

    ``connections`` is the adapters' connection dict, e.g.::

        {
          "filesystem": {"command": "npx",
                          "args": ["-y", "@modelcontextprotocol/server-filesystem", "/repo"],
                          "transport": "stdio"},
          "git": {"command": "uvx", "args": ["mcp-server-git"], "transport": "stdio"},
        }

    Requires ``pip install "langchain-mcp-adapters"``. All SDK coupling is
    isolated in :meth:`_get_tools`, so a library API change touches one method.
    Not exercised in the scaffold tests.
    """

    def __init__(self, connections: dict[str, dict[str, Any]]):
        self._connections = connections
        self._tools_cache: dict[str, Any] | None = None  # name -> langchain BaseTool

    def _run(self, coro):
        import asyncio

        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(coro)
        # Already inside a loop: run the coroutine on a private loop in a thread.
        import threading

        result: dict[str, Any] = {}

        def _worker():
            result["value"] = asyncio.run(coro)

        t = threading.Thread(target=_worker)
        t.start()
        t.join()
        return result["value"]

    def _get_tools(self) -> dict[str, Any]:
        if self._tools_cache is None:
            from langchain_mcp_adapters.client import MultiServerMCPClient  # lazy

            client = MultiServerMCPClient(self._connections)
            tools = self._run(client.get_tools())
            self._tools_cache = {t.name: t for t in tools}
        return self._tools_cache

    def list_tools(self) -> list[MCPToolSpec]:
        specs: list[MCPToolSpec] = []
        for name, tool in self._get_tools().items():
            schema = getattr(tool, "args", None) or getattr(tool, "args_schema", None) or {}
            specs.append(MCPToolSpec(name=name, description=getattr(tool, "description", "") or "",
                                     input_schema=schema if isinstance(schema, dict) else {}))
        return specs

    def call_tool(self, name: str, arguments: dict[str, Any]) -> MCPToolResult:
        tool = self._get_tools().get(name)
        if tool is None:
            return MCPToolResult(name=name, ok=False, error="unknown tool")
        try:
            output = self._run(tool.ainvoke(arguments))
            return MCPToolResult(name=name, ok=True, content=str(output))
        except Exception as exc:  # noqa: BLE001
            return MCPToolResult(name=name, ok=False, error=str(exc))
