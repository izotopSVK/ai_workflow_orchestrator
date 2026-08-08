from __future__ import annotations

from collections.abc import Callable
from typing import Any

from workflows.dev_orchestrator.deps import DevOrchestratorDeps
from workflows.dev_orchestrator.nodes._helpers import advance
from workflows.dev_orchestrator.state import DevOrchestratorState
from workflows.dev_orchestrator.tools.workspace import Workspace
from workflows.models.enums import WorkflowStatus
from workflows.observability.redaction import redact_snippet


def make_apply_node(
    deps: DevOrchestratorDeps,
) -> Callable[[DevOrchestratorState], dict[str, Any]]:
    """Write the proposed diff into the worktree before verification.

    Without this the quality gates would run against unchanged files and finalize
    would commit nothing. A failed apply (malformed diff) is treated like a failed
    gate so the Reflexion loop regenerates the change.
    """

    def apply_node(state: DevOrchestratorState) -> dict[str, Any]:
        ws = state.get("workspace")
        diff = state.get("diff", "")
        if not ws:
            return advance(
                state, "apply", applied=False,
                verify_report={"apply": {"ok": False, "output": "no workspace"}},
                status=WorkflowStatus.FAILED.value,
            )

        ok, output = deps.workspace.apply_patch(Workspace.from_dict(ws), diff)
        if ok:
            return advance(state, "apply", applied=True)

        return advance(
            state, "apply", applied=False,
            verify_report={"apply": {"ok": False, "output": redact_snippet(output)}},
            status=WorkflowStatus.FAILED.value,
        )

    return apply_node
