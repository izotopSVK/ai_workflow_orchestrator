from __future__ import annotations

from workflows.dev_orchestrator.state import DevOrchestratorState
from workflows.models.enums import WorkflowStatus


def _gates_ok(state: DevOrchestratorState) -> bool:
    report = state.get("verify_report") or {}
    return bool(report) and all(r.get("ok", False) for r in report.values())


def route_after_verify(state: DevOrchestratorState) -> str:
    """Green -> human review; red -> reflect & retry until the loop is exhausted."""
    if _gates_ok(state):
        return "review"
    if state.get("iteration", 0) < state.get("max_iterations", 0):
        return "reflect"
    return "finalize"  # give up: report failure


def route_after_human_review(state: DevOrchestratorState) -> str:
    """Parked -> END (await resume); approved -> finalize."""
    if state.get("status") == WorkflowStatus.WAITING_FOR_HUMAN.value:
        return "end"
    return "finalize"
