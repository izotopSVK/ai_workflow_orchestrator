from __future__ import annotations

from langchain_core.messages import AIMessage, ToolMessage

from workflows.dev_orchestrator.mcp_tools import FakeMCPToolProvider, MCPToolResult, MCPToolSpec
from workflows.dev_orchestrator.tool_loop import (
    mcp_specs_to_openai_tools,
    run_tool_loop,
)


class FakeChat:
    """Returns scripted AIMessages on successive invoke() calls."""

    def __init__(self, scripted):
        self._scripted = list(scripted)
        self.calls = 0
        self.seen: list[list] = []

    def invoke(self, messages):
        self.seen.append(list(messages))
        msg = self._scripted[self.calls]
        self.calls += 1
        return msg


def _tool_call(name, args, cid):
    return {"name": name, "args": args, "id": cid, "type": "tool_call"}


# --- spec -> OpenAI tool schema ---------------------------------------------

def test_specs_to_openai_tools():
    specs = [
        MCPToolSpec(name="read_file", description="Read a file",
                    input_schema={"type": "object", "properties": {"path": {"type": "string"}}}),
        MCPToolSpec(name="noschema", description=""),  # no/invalid schema -> default object
    ]
    tools = mcp_specs_to_openai_tools(specs)
    assert tools[0]["type"] == "function"
    assert tools[0]["function"]["name"] == "read_file"
    assert tools[0]["function"]["parameters"]["properties"]["path"]["type"] == "string"
    assert tools[1]["function"]["parameters"] == {"type": "object", "properties": {}, "additionalProperties": True}


# --- the loop ---------------------------------------------------------------

def test_loop_executes_tools_then_stops():
    chat = FakeChat([
        AIMessage(content="", tool_calls=[_tool_call("read_file", {"path": "User.php"}, "1")]),
        AIMessage(content="", tool_calls=[_tool_call("git_diff", {}, "2")]),
        AIMessage(content="done", tool_calls=[]),
    ])
    provider = FakeMCPToolProvider([
        (MCPToolSpec(name="read_file"), lambda a: f"contents of {a['path']}"),
        (MCPToolSpec(name="git_diff"), lambda a: "the diff"),
    ])

    result = run_tool_loop(chat, [("human", "do it")], provider.call_tool, max_steps=6)

    # Two tools were executed, in order.
    assert [s.name for s in result.steps] == ["read_file", "git_diff"]
    assert result.steps[0].content == "contents of User.php"
    assert all(s.ok for s in result.steps)
    # ToolMessages were appended to the conversation for each call.
    tool_msgs = [m for m in result.messages if isinstance(m, ToolMessage)]
    assert [m.tool_call_id for m in tool_msgs] == ["1", "2"]
    # Loop stopped after the assistant answered without tool calls (3 invokes).
    assert chat.calls == 3


def test_loop_reports_tool_errors_but_continues():
    chat = FakeChat([
        AIMessage(content="", tool_calls=[_tool_call("boom", {}, "1")]),
        AIMessage(content="done", tool_calls=[]),
    ])
    provider = FakeMCPToolProvider([
        (MCPToolSpec(name="boom"), lambda a: (_ for _ in ()).throw(RuntimeError("nope"))),
    ])

    result = run_tool_loop(chat, [("human", "x")], provider.call_tool)
    assert not result.steps[0].ok
    tool_msg = [m for m in result.messages if isinstance(m, ToolMessage)][0]
    assert tool_msg.content.startswith("ERROR: nope")


def test_loop_respects_max_steps():
    # Always asks for a tool -> loop must stop at max_steps.
    always = AIMessage(content="", tool_calls=[_tool_call("read_file", {}, "x")])
    chat = FakeChat([always] * 10)
    provider = FakeMCPToolProvider([(MCPToolSpec(name="read_file"), lambda a: "ok")])

    result = run_tool_loop(chat, [("human", "x")], provider.call_tool, max_steps=3)
    assert chat.calls == 3
    assert len(result.steps) == 3


def test_no_tool_calls_returns_immediately():
    chat = FakeChat([AIMessage(content="answer", tool_calls=[])])
    result = run_tool_loop(chat, [("human", "x")], lambda n, a: MCPToolResult(name=n, ok=True))
    assert result.steps == []
    assert chat.calls == 1


# --- node wiring: implement offers MCP tools to the agent -------------------

def test_implement_node_passes_tools_and_executes():
    from workflows.dev_orchestrator.config import DevOrchestratorConfig
    from workflows.dev_orchestrator.deps import DevOrchestratorDeps
    from workflows.dev_orchestrator.llm import FakeDevLLM
    from workflows.dev_orchestrator.nodes.implement import make_implement_node
    from workflows.dev_orchestrator.tools.memory import InMemoryMemoryStore
    from workflows.dev_orchestrator.tools.php_toolchain import FakePhpToolchain
    from workflows.dev_orchestrator.tools.workspace import FakeWorkspaceManager

    mcp = FakeMCPToolProvider([(MCPToolSpec(name="read_file"), lambda a: "contents")])
    deps = DevOrchestratorDeps(
        llm=FakeDevLLM(),
        workspace=FakeWorkspaceManager(),
        php=FakePhpToolchain(),
        memory=InMemoryMemoryStore(),
        config=DevOrchestratorConfig(),
        mcp=mcp,
    )
    node = make_implement_node(deps)
    out = node({"goal": "g", "plan": [{"id": "s", "description": "d"}], "iteration": 0})

    # The implement node offered the MCP tool and the agent executed it.
    assert mcp.calls == [("read_file", {})]
    assert out["diff"]  # a diff was produced
    assert "implement" in out["completed_steps"]
