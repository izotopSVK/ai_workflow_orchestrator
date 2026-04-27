from __future__ import annotations

from typing import Any, NotRequired, TypedDict


class AgentWorkflowState(TypedDict):
    workflow_id: str
    goal: str
    status: str
    current_node: NotRequired[str]
    plan: NotRequired[list[dict[str, Any]]]
    completed_steps: list[str]
    failed_steps: list[str]
    artifacts: list[dict[str, Any]]
    tool_calls: list[dict[str, Any]]
    errors: list[dict[str, Any]]
    pending_approval_id: NotRequired[str | None]
    budget: dict[str, Any]
    budget_used: dict[str, Any]
    final_result: NotRequired[dict[str, Any]]
