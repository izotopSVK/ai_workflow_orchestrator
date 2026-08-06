from __future__ import annotations

import pytest
from langgraph.checkpoint.memory import InMemorySaver

from workflows.dev_orchestrator.builder import build_dev_orchestrator_graph
from workflows.dev_orchestrator.config import DevOrchestratorConfig
from workflows.dev_orchestrator.deps import DevOrchestratorDeps
from workflows.dev_orchestrator.llm import FakeDevLLM
from workflows.dev_orchestrator.schemas import Lesson, ToolResult
from workflows.dev_orchestrator.service import DevOrchestratorService
from workflows.dev_orchestrator.tools.memory import InMemoryMemoryStore
from workflows.dev_orchestrator.tools.php_toolchain import FakePhpToolchain
from workflows.dev_orchestrator.tools.workspace import FakeWorkspaceManager
from workflows.models.enums import WorkflowStatus


def make_service(*, config, php=None, memory=None, workspace=None):
    deps = DevOrchestratorDeps(
        llm=FakeDevLLM(),
        workspace=workspace or FakeWorkspaceManager(),
        php=php or FakePhpToolchain(),
        memory=memory or InMemoryMemoryStore(),
        config=config,
    )
    graph = build_dev_orchestrator_graph(checkpointer=InMemorySaver(), deps=deps)
    return DevOrchestratorService(graph=graph, config=config), deps


def test_happy_path_completes_and_commits():
    config = DevOrchestratorConfig(require_human_review=False)
    workspace = FakeWorkspaceManager()
    service, deps = make_service(config=config, workspace=workspace)

    state = service.start(goal="Migrate User model to PHP 8.4")

    assert state["status"] == WorkflowStatus.COMPLETED.value
    # Every stage ran, in order, ending with teardown.
    for step in ["bootstrap", "retrieve", "analyze", "plan", "implement",
                 "verify", "finalize", "learn", "teardown"]:
        assert step in state["completed_steps"]
    assert state["final_result"]["outcome"] == "completed"
    assert state["final_result"]["commit"] is not None
    # Worktree provisioned then released.
    assert workspace.commits and workspace.removed


def test_bootstrap_provisions_workspace():
    config = DevOrchestratorConfig(require_human_review=False)
    workspace = FakeWorkspaceManager()
    service, _ = make_service(config=config, workspace=workspace)

    state = service.start(goal="Refactor DAO layer")

    ws = state["workspace"]
    assert ws["branch"].startswith(config.branch_prefix)
    assert ws["copied"] == config.copy_globs
    assert set(ws["symlinks"]) == set(config.symlink_map.keys())


def test_parks_for_human_review_then_resumes():
    config = DevOrchestratorConfig(require_human_review=True)
    service, _ = make_service(config=config)

    parked = service.start(goal="Introduce constructor DI in controllers")
    assert parked["status"] == WorkflowStatus.WAITING_FOR_HUMAN.value
    assert parked.get("pending_approval_id")
    assert "finalize" not in parked["completed_steps"]

    resumed = service.approve(parked["workflow_id"])
    assert resumed["status"] == WorkflowStatus.COMPLETED.value
    assert "finalize" in resumed["completed_steps"]
    assert resumed["final_result"]["commit"] is not None


def test_reflexion_loop_recovers_after_failed_gate():
    # PHPStan fails on the first verify, passes on the retry.
    php = FakePhpToolchain(results={
        "phpstan": [
            ToolResult(tool="phpstan", ok=False, findings=["dynamic property $foo"]),
            ToolResult(tool="phpstan", ok=True),
        ],
    })
    memory = InMemoryMemoryStore()
    config = DevOrchestratorConfig(require_human_review=False, max_iterations=4)
    service, _ = make_service(config=config, php=php, memory=memory)

    state = service.start(goal="Fix dynamic properties on CActiveRecord")

    assert state["status"] == WorkflowStatus.COMPLETED.value
    assert state["iteration"] == 2  # one retry
    assert len(state["reflections"]) == 1
    assert "reflect" in state["completed_steps"]
    # The lesson was persisted and reinforced on success.
    assert memory.retrieve_lessons("dynamic property phpstan", 5)


def test_gives_up_after_exhausting_iterations():
    php = FakePhpToolchain(results={
        "phpstan": ToolResult(tool="phpstan", ok=False, findings=["still broken"]),
    })
    memory = InMemoryMemoryStore()
    config = DevOrchestratorConfig(require_human_review=False, max_iterations=2)
    service, _ = make_service(config=config, php=php, memory=memory)

    state = service.start(goal="Impossible migration")

    assert state["status"] == WorkflowStatus.FAILED.value
    assert state["iteration"] == 2
    assert state["final_result"]["outcome"] == "failed"
    assert state["final_result"]["commit"] is None
    # An episode is still recorded (we learn from failures too).
    assert memory.retrieve_episodes("impossible migration", 5)


def test_self_learning_retrieval_feeds_planning():
    memory = InMemoryMemoryStore()
    memory.record_lesson(Lesson(
        title="User model migration to PHP 8.4",
        detail="each() removed; add AllowDynamicProperties",
        tags=["user", "model", "php84"],
    ))
    config = DevOrchestratorConfig(require_human_review=False)
    service, _ = make_service(config=config, memory=memory)

    state = service.start(goal="Migrate User model to PHP 8.4")

    assert state["retrieved_lessons"], "prior lesson should be retrieved into the run"
    assert "user" in state["retrieved_lessons"][0]["tags"]


@pytest.mark.parametrize("require_review", [True, False])
def test_get_state_returns_snapshot(require_review):
    config = DevOrchestratorConfig(require_human_review=require_review)
    service, _ = make_service(config=config)

    started = service.start(goal="Any goal")
    snapshot = service.get_state(started["workflow_id"])

    assert snapshot is not None
    assert snapshot["workflow_id"] == started["workflow_id"]
