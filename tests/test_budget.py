from __future__ import annotations

import time

from langgraph.checkpoint.memory import InMemorySaver

from workflows.dev_orchestrator.builder import build_dev_orchestrator_graph
from workflows.dev_orchestrator.config import DevOrchestratorConfig
from workflows.dev_orchestrator.factory import build_fake_deps
from workflows.dev_orchestrator.routing import over_budget
from workflows.dev_orchestrator.service import DevOrchestratorService
from workflows.models.enums import WorkflowStatus


# --- over_budget unit -------------------------------------------------------

def test_over_budget_llm_calls():
    assert over_budget({"max_llm_calls": 3, "budget_used": {"llm_calls": 3}})
    assert not over_budget({"max_llm_calls": 3, "budget_used": {"llm_calls": 2}})


def test_over_budget_unlimited_when_zero():
    assert not over_budget({"max_llm_calls": 0, "budget_used": {"llm_calls": 999}})


def test_over_budget_runtime():
    assert over_budget({"max_runtime_seconds": 1, "started_at": time.time() - 10})
    assert not over_budget({"max_runtime_seconds": 60, "started_at": time.time()})


def test_over_budget_missing_keys_is_false():
    assert not over_budget({})


# --- enforcement in a run ---------------------------------------------------

def test_llm_call_budget_stops_the_run():
    config = DevOrchestratorConfig(require_human_review=False, max_llm_calls=2)
    graph = build_dev_orchestrator_graph(checkpointer=InMemorySaver(), deps=build_fake_deps(config))
    state = DevOrchestratorService(graph=graph, config=config).start(goal="anything")

    assert state["status"] == WorkflowStatus.FAILED.value
    assert state["final_result"]["budget_exceeded"] is True
    assert state["final_result"]["commit"] is None
    # analyze, plan, implement each counted -> loop was cut off at the budget.
    assert state["budget_used"]["llm_calls"] >= 2
    assert "verify" not in state["completed_steps"]  # stopped before more LLM work


def test_generous_budget_completes():
    config = DevOrchestratorConfig(require_human_review=False, max_llm_calls=50)
    graph = build_dev_orchestrator_graph(checkpointer=InMemorySaver(), deps=build_fake_deps(config))
    state = DevOrchestratorService(graph=graph, config=config).start(goal="anything")

    assert state["status"] == WorkflowStatus.COMPLETED.value
    assert state["final_result"]["budget_exceeded"] is False
