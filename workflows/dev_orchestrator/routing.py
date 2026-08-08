from __future__ import annotations

import time

from workflows.dev_orchestrator.state import DevOrchestratorState
from workflows.models.enums import WorkflowStatus


def _gates_ok(state: DevOrchestratorState) -> bool:
    report = state.get("verify_report") or {}
    return bool(report) and all(r.get("ok", False) for r in report.values())


def over_budget(state: DevOrchestratorState) -> bool:
    """True if the run has hit its LLM-call or runtime budget (0 = unlimited)."""
    max_calls = state.get("max_llm_calls", 0)
    if max_calls and state.get("budget_used", {}).get("llm_calls", 0) >= max_calls:
        return True
    max_runtime = state.get("max_runtime_seconds", 0)
    started = state.get("started_at")
    if max_runtime and started and (time.time() - started) >= max_runtime:
        return True
    return False


def route_after_apply(state: DevOrchestratorState) -> str:
    """Applied cleanly -> verify; failed patch -> reflect & retry (or give up)."""
    if over_budget(state):
        return "finalize"
    if state.get("applied", False):
        return "verify"
    if state.get("iteration", 0) < state.get("max_iterations", 0):
        return "reflect"
    return "finalize"


def route_after_verify(state: DevOrchestratorState) -> str:
    """Green -> human review; red -> reflect & retry until budget/iterations run out."""
    if _gates_ok(state):
        return "review"  # a passing result is never discarded on budget
    if over_budget(state):
        return "finalize"
    if state.get("iteration", 0) < state.get("max_iterations", 0):
        return "reflect"
    return "finalize"  # give up: report failure


def route_after_human_review(state: DevOrchestratorState) -> str:
    """Parked -> END (await resume); approved -> finalize."""
    if state.get("status") == WorkflowStatus.WAITING_FOR_HUMAN.value:
        return "end"
    return "finalize"
