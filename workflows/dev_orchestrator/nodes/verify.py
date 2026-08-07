from __future__ import annotations

from collections.abc import Callable
from typing import Any

from workflows.dev_orchestrator.deps import DevOrchestratorDeps
from workflows.dev_orchestrator.state import DevOrchestratorState
from workflows.models.enums import WorkflowStatus


def make_verify_node(
    deps: DevOrchestratorDeps,
) -> Callable[[DevOrchestratorState], dict[str, Any]]:
    """Run the deterministic quality gates and aggregate a verify report.

    Gate order is cheap-to-expensive: php -l -> Rector -> PHPStan -> PHP-CS-Fixer
    -> PHPUnit -> SOLID review. Any failing gate marks the report not-ok, which
    routes the graph into the reflect/retry loop.
    """

    def verify_node(state: DevOrchestratorState) -> dict[str, Any]:
        ws = state.get("workspace") or {}
        ws_path = ws.get("path", "")
        paths = state.get("target_files", []) or []
        cfg = deps.config

        report: dict[str, Any] = {}
        report["phplint"] = deps.php.lint(ws_path, paths).model_dump()
        report["rector"] = deps.php.rector(ws_path, paths, cfg.rector_sets).model_dump()
        report["phpstan"] = deps.php.phpstan(ws_path, paths, cfg.phpstan_level).model_dump()
        report["cs_fixer"] = deps.php.cs_fixer(ws_path, paths).model_dump()
        report["phpunit"] = deps.php.phpunit(ws_path, paths).model_dump()

        solid = deps.llm.review_solid(
            diff=state.get("diff", ""),
            system_extra=state.get("agent_instructions", ""),
        )
        report["solid"] = {"ok": solid.passed, "score": solid.score,
                           "violations": [v.model_dump() for v in solid.violations]}

        gates_ok = all(r.get("ok", False) for r in report.values())

        completed = list(state.get("completed_steps", []))
        completed.append("verify")

        return {
            "verify_report": report,
            "current_node": "verify",
            "completed_steps": completed,
            "status": WorkflowStatus.RUNNING.value if gates_ok else WorkflowStatus.FAILED.value,
        }

    return verify_node
