from __future__ import annotations

from langgraph.checkpoint.memory import InMemorySaver

from workflows.dev_orchestrator.builder import build_dev_orchestrator_graph
from workflows.dev_orchestrator.config import DevOrchestratorConfig
from workflows.dev_orchestrator.deps import DevOrchestratorDeps
from workflows.dev_orchestrator.factory import build_mcp_provider
from workflows.dev_orchestrator.llm import FakeDevLLM
from workflows.dev_orchestrator.mcp_tools import (
    FakeMCPToolProvider,
    MCPToolSpec,
    MultiServerMCPToolProvider,
    NoMCPToolProvider,
)
from workflows.dev_orchestrator.nodes.load_context import make_load_context_node
from workflows.dev_orchestrator.service import DevOrchestratorService
from workflows.dev_orchestrator.tools.memory import InMemoryMemoryStore
from workflows.dev_orchestrator.tools.php_toolchain import FakePhpToolchain
from workflows.dev_orchestrator.tools.workspace import FakeWorkspaceManager


def _fake_mcp():
    return FakeMCPToolProvider([
        (MCPToolSpec(name="git_diff", description="Show the working tree diff", server="git"),
         lambda args: f"diff for {args.get('path', '.')}"),
        (MCPToolSpec(name="read_file", description="Read a file", server="filesystem"),
         lambda args: f"contents of {args['path']}"),
    ])


# --- provider basics --------------------------------------------------------

def test_no_provider_lists_nothing_and_errors_on_call():
    p = NoMCPToolProvider()
    assert p.list_tools() == []
    res = p.call_tool("anything", {})
    assert not res.ok and "No MCP provider" in res.error


def test_fake_provider_lists_and_calls():
    p = _fake_mcp()
    names = {t.name for t in p.list_tools()}
    assert names == {"git_diff", "read_file"}

    res = p.call_tool("read_file", {"path": "protected/models/User.php"})
    assert res.ok
    assert res.content == "contents of protected/models/User.php"
    assert p.calls == [("read_file", {"path": "protected/models/User.php"})]


def test_fake_provider_unknown_tool():
    res = _fake_mcp().call_tool("nope", {})
    assert not res.ok and res.error == "unknown tool"


def test_fake_provider_surfaces_handler_error():
    p = FakeMCPToolProvider([
        (MCPToolSpec(name="boom"), lambda args: (_ for _ in ()).throw(RuntimeError("kaboom"))),
    ])
    res = p.call_tool("boom", {})
    assert not res.ok and "kaboom" in res.error


# --- factory ----------------------------------------------------------------

def test_build_mcp_provider_selects_impl():
    assert isinstance(build_mcp_provider(DevOrchestratorConfig()), NoMCPToolProvider)
    configured = DevOrchestratorConfig(mcp_servers={
        "git": {"command": "uvx", "args": ["mcp-server-git"], "transport": "stdio"},
    })
    assert isinstance(build_mcp_provider(configured), MultiServerMCPToolProvider)


# --- load_context surfaces MCP tools to agents ------------------------------

def _deps(mcp):
    return DevOrchestratorDeps(
        llm=FakeDevLLM(),
        workspace=FakeWorkspaceManager(),
        php=FakePhpToolchain(),
        memory=InMemoryMemoryStore(),
        config=DevOrchestratorConfig(),
        mcp=mcp,
    )


def test_load_context_injects_mcp_catalog():
    node = make_load_context_node(_deps(_fake_mcp()))
    out = node({"goal": "migrate User model", "workspace": {"path": "/nonexistent"}})

    tool_names = {t["name"] for t in out["mcp_tools"]}
    assert tool_names == {"git_diff", "read_file"}
    assert "Available external tools (via MCP)" in out["agent_instructions"]
    assert "git_diff: Show the working tree diff" in out["agent_instructions"]


def test_load_context_without_mcp_is_empty():
    node = make_load_context_node(_deps(None))  # falls back to NoMCPToolProvider
    out = node({"goal": "x", "workspace": {"path": "/nonexistent"}})
    assert out["mcp_tools"] == []


def test_graph_runs_with_mcp_provider():
    config = DevOrchestratorConfig(require_human_review=False)
    deps = DevOrchestratorDeps(
        llm=FakeDevLLM(),
        workspace=FakeWorkspaceManager(),
        php=FakePhpToolchain(),
        memory=InMemoryMemoryStore(),
        config=config,
        mcp=_fake_mcp(),
    )
    graph = build_dev_orchestrator_graph(checkpointer=InMemorySaver(), deps=deps)
    state = DevOrchestratorService(graph=graph, config=config).start(goal="Migrate models")
    assert state["status"] == "completed"
    assert {t["name"] for t in state["mcp_tools"]} == {"git_diff", "read_file"}
