# MCP (Model Context Protocol) — client support

The dev orchestrator can consume tools served by external **MCP servers**
(filesystem, git, docs, DB introspection, …). It discovers those tools at the
start of a run and makes the agents aware of them.

> Direction: **client** (the orchestrator uses external MCP tools). Exposing the
> orchestrator itself *as* an MCP server is a separate, not-yet-built direction.

## Configure servers

Set `DevOrchestratorConfig.mcp_servers` to a
[`langchain-mcp-adapters`](https://github.com/langchain-ai/langchain-mcp-adapters)
connection map:

```python
config = DevOrchestratorConfig(
    mcp_servers={
        "filesystem": {
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path/to/repo"],
            "transport": "stdio",
        },
        "git": {"command": "uvx", "args": ["mcp-server-git"], "transport": "stdio"},
        # HTTP servers work too:
        # "docs": {"url": "https://mcp.example.com/mcp", "transport": "streamable_http"},
    },
)
```

Install the adapter: `pip install -e ".[mcp]"`.

## What happens at runtime

- `load_context` calls `deps.mcp.list_tools()` and:
  - stores the tool catalog (name/description/server) in `state["mcp_tools"]`
    (checkpointed / auditable), and
  - appends an **"Available external tools (via MCP)"** section to
    `agent_instructions`, so every agent's system prompt knows the tools exist.
- Any node can invoke a tool via `deps.mcp.call_tool(name, arguments)`, which
  returns a uniform `MCPToolResult(name, ok, content, error)`.

## Design / DI

`workflows/dev_orchestrator/mcp_tools.py` defines the `MCPToolProvider` Protocol:

| Impl | Use |
|------|-----|
| `NoMCPToolProvider` | default; no servers, no dependency |
| `FakeMCPToolProvider` | scriptable `(spec, handler)` pairs for tests |
| `MultiServerMCPToolProvider` | real; wraps `langchain-mcp-adapters` (lazy import) |

The provider is **sync** like the rest of the package; the real implementation
runs the async MCP client internally. All SDK coupling is isolated in
`MultiServerMCPToolProvider._get_tools`, so a library API change touches one
method. Wired via `factory.build_mcp_provider` into `build_real_deps`; unset in
the fake deps (tests), where the node falls back to `NoMCPToolProvider`.

## Current scope & next step

This scaffold provides **discovery + invocation + agent awareness**. The agents
do not yet *autonomously decide* to call MCP tools mid-generation — that needs a
function-calling agent loop (Copilot supports tool calls, but the current graph
uses fixed structured-output roles). Natural next step: a tool-calling variant of
the `implement`/`analyze` nodes that lets the model choose MCP tools, executed via
`deps.mcp.call_tool`. Tested in `tests/test_mcp.py` (8 tests).
