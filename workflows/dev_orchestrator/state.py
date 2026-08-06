from __future__ import annotations

from typing import Any, NotRequired, TypedDict


class DevOrchestratorState(TypedDict):
    """Graph state for the self-learning Yii 1.1 -> PHP 8.4 dev orchestrator."""

    workflow_id: str
    goal: str
    status: str
    current_node: NotRequired[str]

    # Isolated workspace created by the bootstrap node.
    # {"path", "branch", "base_ref", "copied": [...], "symlinks": [...]}
    workspace: NotRequired[dict[str, Any]]

    # Self-learning: lessons/episodes pulled from memory before planning.
    retrieved_lessons: list[dict[str, Any]]

    # Analyze + plan output.
    target_files: list[str]
    plan: NotRequired[list[dict[str, Any]]]

    # Latest proposed change and its verification report.
    diff: NotRequired[str]
    verify_report: NotRequired[dict[str, Any]]

    # Reflexion loop bookkeeping.
    iteration: int
    max_iterations: int
    reflections: list[dict[str, Any]]

    completed_steps: list[str]
    errors: list[dict[str, Any]]
    pending_approval_id: NotRequired[str | None]
    final_result: NotRequired[dict[str, Any]]
