from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from workflows.dev_orchestrator.mcp_tools import MCPToolResult, MCPToolSpec
from workflows.dev_orchestrator.schemas import (
    AnalysisOutput,
    ImplementOutput,
    Lesson,
    PlanOutput,
    PlanStep,
    PromptContext,
    SolidReview,
)


class DevLLM(Protocol):
    """LLM roles used by the dev orchestrator.

    The LLM proposes; deterministic tools dispose. It never decides whether a
    change is correct — that is the PHP toolchain's job. Cross-cutting per-run
    inputs (lessons, reflections, project instructions) come in via ``ctx``.
    """

    def analyze(
        self,
        *,
        goal: str,
        file_hints: list[str],
        ctx: PromptContext,
        tools: list[MCPToolSpec] | None = None,
        execute: Callable[[str, dict], MCPToolResult] | None = None,
    ) -> AnalysisOutput: ...

    def plan(self, *, goal: str, analysis: AnalysisOutput, ctx: PromptContext) -> PlanOutput: ...

    def implement(
        self,
        *,
        goal: str,
        plan: PlanOutput,
        ctx: PromptContext,
        tools: list[MCPToolSpec] | None = None,
        execute: Callable[[str, dict], MCPToolResult] | None = None,
    ) -> ImplementOutput: ...

    def review_solid(self, *, diff: str, ctx: PromptContext) -> SolidReview: ...

    def reflect(self, *, goal: str, verify_report: dict, ctx: PromptContext) -> Lesson: ...


class FakeDevLLM:
    """Deterministic DevLLM for tests and offline runs."""

    def analyze(self, *, goal, file_hints, ctx, tools=None, execute=None) -> AnalysisOutput:
        note = ""
        if tools and execute is not None:
            res = execute(tools[0].name, {})
            note = f" (used {tools[0].name}: {'ok' if res.ok else res.error})"
        return AnalysisOutput(
            target_files=file_hints or ["protected/models/User.php"],
            risks=[
                "PHP 8.4: dynamic properties deprecated on CComponent subclasses",
                "PHP 8.4: each() removed",
            ],
            notes=f"Analyzed goal: {goal}{note}",
        )

    def plan(self, *, goal, analysis, ctx) -> PlanOutput:
        steps = [
            PlanStep(
                id="migrate_syntax",
                description="Apply Rector PHP_84 set to target files",
                target_file=analysis.target_files[0] if analysis.target_files else None,
                expected_output="PHP 8.4 compatible syntax",
            ),
            PlanStep(
                id="apply_solid",
                description="Introduce constructor DI, split responsibilities",
                expected_output="SOLID-compliant classes",
            ),
            PlanStep(
                id="tests",
                description="Ensure PHPUnit suite passes",
                expected_output="Green test run",
            ),
        ]
        return PlanOutput(steps=steps, confidence=0.9)

    def implement(self, *, goal, plan, ctx, tools=None, execute=None) -> ImplementOutput:
        touched = [s.target_file for s in plan.steps if s.target_file] or ["protected/models/User.php"]
        note = ""
        # Simulate a tool-using agent: if MCP tools are offered, call the first one.
        if tools and execute is not None:
            res = execute(tools[0].name, {})
            note = f" (used {tools[0].name}: {'ok' if res.ok else res.error})"
        return ImplementOutput(
            diff="--- a/file\n+++ b/file\n@@\n-legacy\n+modernized\n",
            summary=f"Implemented {len(plan.steps)} steps for: {goal}{note}",
            touched_files=list(dict.fromkeys(touched)),
        )

    def review_solid(self, *, diff, ctx) -> SolidReview:
        return SolidReview(score=1.0, violations=[])

    def reflect(self, *, goal, verify_report, ctx) -> Lesson:
        failing = [k for k, v in (verify_report or {}).items() if isinstance(v, dict) and not v.get("ok", True)]
        tag = failing[0] if failing else "general"
        return Lesson(
            title=f"Fix {tag} before retrying",
            detail=f"Verify failed on {failing or ['unknown']} for goal: {goal}",
            tags=["yii1", "php84", tag],
        )


# The real, enterprise DevLLM implementation lives in
# ``workflows.dev_orchestrator.dev_llm.GitHubCopilotLLM`` (GitHub Copilot,
# SSO-compatible). It is defined there to keep langchain-openai optional for the
# Fake path used in tests.
