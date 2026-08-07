from __future__ import annotations

from collections.abc import Callable
from typing import Any

from workflows.dev_orchestrator.config import DevOrchestratorConfig
from workflows.dev_orchestrator.deps import DevOrchestratorDeps
from workflows.dev_orchestrator.nodes._helpers import advance, context_from_state
from workflows.dev_orchestrator.schemas import ToolResult
from workflows.dev_orchestrator.state import DevOrchestratorState
from workflows.models.enums import WorkflowStatus

# The deterministic quality gates, cheap-to-expensive. Add or remove a gate by
# editing this list — the verify node iterates it and never hardcodes the set.
PhpGate = Callable[["DevOrchestratorDeps", str, list[str], DevOrchestratorConfig], ToolResult]

PHP_GATES: list[tuple[str, PhpGate]] = [
    ("phplint", lambda deps, ws, paths, cfg: deps.php.lint(ws, paths)),
    ("rector", lambda deps, ws, paths, cfg: deps.php.rector(ws, paths, cfg.rector_sets)),
    ("phpstan", lambda deps, ws, paths, cfg: deps.php.phpstan(ws, paths, cfg.phpstan_level)),
    ("cs_fixer", lambda deps, ws, paths, cfg: deps.php.cs_fixer(ws, paths)),
    ("phpunit", lambda deps, ws, paths, cfg: deps.php.phpunit(ws, paths)),
]


def make_verify_node(
    deps: DevOrchestratorDeps,
) -> Callable[[DevOrchestratorState], dict[str, Any]]:
    """Run the deterministic quality gates + SOLID review; aggregate a report.

    Any failing gate marks the report not-ok, which routes the graph into the
    reflect/retry loop.
    """

    def verify_node(state: DevOrchestratorState) -> dict[str, Any]:
        ws_path = (state.get("workspace") or {}).get("path", "")
        paths = state.get("target_files", []) or []
        cfg = deps.config

        report: dict[str, Any] = {
            name: gate(deps, ws_path, paths, cfg).model_dump()
            for name, gate in PHP_GATES
        }

        solid = deps.llm.review_solid(diff=state.get("diff", ""), ctx=context_from_state(state))
        report["solid"] = {
            "ok": solid.passed,
            "score": solid.score,
            "violations": [v.model_dump() for v in solid.violations],
        }

        gates_ok = all(r.get("ok", False) for r in report.values())
        status = WorkflowStatus.RUNNING.value if gates_ok else WorkflowStatus.FAILED.value
        return advance(state, "verify", verify_report=report, status=status)

    return verify_node
