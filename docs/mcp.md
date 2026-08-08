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
- The **`analyze` and `implement` agents use a function-calling loop**: the MCP
  tools are bound to the Copilot model; while the model emits tool calls they are
  executed via `deps.mcp.call_tool` and the results fed back, until the model
  answers without a tool call (bounded by `config.max_tool_steps`). The enriched
  conversation is then coerced into the structured result. (analyze reads files /
  git to decide target files & risks; implement reads while writing the diff.)
- Any node can also invoke a tool directly via `deps.mcp.call_tool(name, args)`,
  which returns a uniform `MCPToolResult(name, ok, content, error)`.

## Function-calling loop

`workflows/dev_orchestrator/tool_loop.py` holds `run_tool_loop(chat, messages,
execute, max_steps)` — a transport-agnostic loop that takes any object with
`invoke(messages) -> AIMessage` and an `execute(name, args)` callable, so it is
unit-tested with a fake chat and no network (only `langchain_core` messages).
It is driven by the shared `GitHubCopilotLLM._structured(..., tools=, execute=)`
helper — binds the tools (`bind_tools`), runs the loop, then does one final
structured-output call — so any role can opt in with one argument. When no MCP
tools are configured it falls back to the plain single-shot structured call.

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

## Scope

Discovery + agent awareness + an autonomous **function-calling loop** on the
`analyze` and `implement` agents are implemented. The remaining roles (`plan`,
`review_solid`, `reflect`) still use single-shot structured output; enabling the
loop for any of them is one argument to `_structured` plus passing tools from the
node. Tested in `tests/test_mcp.py` and `tests/test_tool_loop.py`.
