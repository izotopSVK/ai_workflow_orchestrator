from __future__ import annotations

from typing import Protocol

from workflows.dev_orchestrator.schemas import (
    AnalysisOutput,
    ImplementOutput,
    Lesson,
    PlanOutput,
    PlanStep,
    SolidReview,
)


class DevLLM(Protocol):
    """LLM roles used by the dev orchestrator.

    The LLM proposes; deterministic tools dispose. It never decides whether a
    change is correct — that is the PHP toolchain's job.
    """

    def analyze(self, *, goal: str, lessons: list[Lesson], file_hints: list[str]) -> AnalysisOutput: ...

    def plan(self, *, goal: str, analysis: AnalysisOutput, lessons: list[Lesson]) -> PlanOutput: ...

    def implement(
        self, *, goal: str, plan: PlanOutput, reflections: list[str], lessons: list[Lesson]
    ) -> ImplementOutput: ...

    def review_solid(self, *, diff: str) -> SolidReview: ...

    def reflect(self, *, goal: str, verify_report: dict) -> Lesson: ...


class FakeDevLLM:
    """Deterministic DevLLM for tests and offline runs."""

    def analyze(self, *, goal, lessons, file_hints) -> AnalysisOutput:
        return AnalysisOutput(
            target_files=file_hints or ["protected/models/User.php"],
            risks=[
                "PHP 8.4: dynamic properties deprecated on CComponent subclasses",
                "PHP 8.4: each() removed",
            ],
            notes=f"Analyzed goal: {goal}",
        )

    def plan(self, *, goal, analysis, lessons) -> PlanOutput:
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

    def implement(self, *, goal, plan, reflections, lessons) -> ImplementOutput:
        touched = [s.target_file for s in plan.steps if s.target_file] or ["protected/models/User.php"]
        return ImplementOutput(
            diff="--- a/file\n+++ b/file\n@@\n-legacy\n+modernized\n",
            summary=f"Implemented {len(plan.steps)} steps for: {goal}",
            touched_files=list(dict.fromkeys(touched)),
        )

    def review_solid(self, *, diff) -> SolidReview:
        return SolidReview(score=1.0, violations=[])

    def reflect(self, *, goal, verify_report) -> Lesson:
        failing = [k for k, v in (verify_report or {}).items() if isinstance(v, dict) and not v.get("ok", True)]
        tag = failing[0] if failing else "general"
        return Lesson(
            title=f"Fix {tag} before retrying",
            detail=f"Verify failed on {failing or ['unknown']} for goal: {goal}",
            tags=["yii1", "php84", tag],
        )


class OllamaDevLLM:  # pragma: no cover - requires a running Ollama server
    """Real DevLLM backed by a local model via langchain-ollama.

    Structured output per role; prompts are intentionally omitted from the
    scaffold and filled in when the target repo is wired up.
    """

    def __init__(self, *, model: str, base_url: str):
        from langchain_ollama import ChatOllama

        self._chat = ChatOllama(model=model, base_url=base_url, temperature=0.0)

    def _structured(self, schema, prompt):
        result = self._chat.with_structured_output(schema).invoke(prompt)
        return result if isinstance(result, schema) else schema.model_validate(result)

    def analyze(self, *, goal, lessons, file_hints) -> AnalysisOutput:
        raise NotImplementedError("Fill in analyze prompt when target repo is configured")

    def plan(self, *, goal, analysis, lessons) -> PlanOutput:
        raise NotImplementedError

    def implement(self, *, goal, plan, reflections, lessons) -> ImplementOutput:
        raise NotImplementedError

    def review_solid(self, *, diff) -> SolidReview:
        raise NotImplementedError

    def reflect(self, *, goal, verify_report) -> Lesson:
        raise NotImplementedError
