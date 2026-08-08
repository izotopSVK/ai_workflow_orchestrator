from __future__ import annotations

from langgraph.checkpoint.memory import InMemorySaver

from workflows.dev_orchestrator.builder import build_dev_orchestrator_graph
from workflows.dev_orchestrator.config import DevOrchestratorConfig
from workflows.dev_orchestrator.deps import DevOrchestratorDeps
from workflows.dev_orchestrator.llm import FakeDevLLM
from workflows.dev_orchestrator.service import DevOrchestratorService
from workflows.dev_orchestrator.tools.memory import InMemoryMemoryStore
from workflows.dev_orchestrator.tools.php_toolchain import FakePhpToolchain
from workflows.dev_orchestrator.tools.workspace import FakeWorkspaceManager
from workflows.models.enums import WorkflowStatus


def _service(*, workspace, config):
    deps = DevOrchestratorDeps(
        llm=FakeDevLLM(),
        workspace=workspace,
        php=FakePhpToolchain(),
        memory=InMemoryMemoryStore(),
        config=config,
    )
    graph = build_dev_orchestrator_graph(checkpointer=InMemorySaver(), deps=deps)
    return DevOrchestratorService(graph=graph, config=config)


def test_diff_is_applied_to_worktree_before_verify():
    ws = FakeWorkspaceManager()
    service = _service(workspace=ws, config=DevOrchestratorConfig(require_human_review=False))
    state = service.start(goal="Migrate User model")

    assert state["status"] == WorkflowStatus.COMPLETED.value
    assert state["applied"] is True
    assert "apply" in state["completed_steps"]
    # The implement diff was actually written to the worktree, and only then committed.
    assert ws.applied and ws.applied[0].startswith("--- a/file")
    assert ws.commits


def test_failed_patch_retries_then_gives_up():
    ws = FakeWorkspaceManager()
    ws.apply_ok = False  # every `git apply` fails
    config = DevOrchestratorConfig(require_human_review=False, max_iterations=2)
    state = _service(workspace=ws, config=config).start(goal="Bad diff")

    assert state["status"] == WorkflowStatus.FAILED.value
    assert state["applied"] is False
    assert state["final_result"]["outcome"] == "failed"
    assert state["final_result"]["commit"] is None       # nothing committed
    assert state["verify_report"]["apply"]["ok"] is False
    assert "reflect" in state["completed_steps"]          # it retried via Reflexion
    assert state["iteration"] == 2                        # bounded by max_iterations
