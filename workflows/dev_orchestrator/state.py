from __future__ import annotations

from typing import Any, NotRequired, TypedDict


class DevOrchestratorState(TypedDict):
    """Graph state for the self-learning Yii 1.1 -> PHP 8.4 dev orchestrator.

    Convention: fields initialized in ``DevOrchestratorService.start`` are
    required; everything a node produces later is ``NotRequired``.
    """

    # --- Initialized at start (always present) ---------------------------
    workflow_id: str
    goal: str
    status: str
    retrieved_lessons: list[dict[str, Any]]
    target_files: list[str]
    iteration: int
    max_iterations: int
    reflections: list[dict[str, Any]]
    completed_steps: list[str]
    errors: list[dict[str, Any]]
    pending_approval_id: NotRequired[str | None]  # init'd to None, cleared/set later

    # --- Produced by nodes (present once that node has run) --------------
    current_node: NotRequired[str]

    # Isolated workspace created by the bootstrap node:
    # {"path", "branch", "base_ref", "copied": [...], "symlinks": [...]}
    workspace: NotRequired[dict[str, Any]]

    # Project instructions (AGENTS.md standard & friends) + skills, loaded from
    # the worktree by load_context and composed into every agent's prompt.
    instructions: NotRequired[str]
    selected_skills: NotRequired[list[dict[str, Any]]]
    agent_instructions: NotRequired[str]
    mcp_tools: NotRequired[list[dict[str, Any]]]     # external MCP tools discovered

    plan: NotRequired[list[dict[str, Any]]]          # from plan
    diff: NotRequired[str]                            # from implement
    applied: NotRequired[bool]                        # from apply
    verify_report: NotRequired[dict[str, Any]]        # from verify
    final_result: NotRequired[dict[str, Any]]         # from finalize
