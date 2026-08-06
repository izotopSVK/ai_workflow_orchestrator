"""GitHub Copilot DevLLM for the self-learning dev orchestrator.

Implements the ``DevLLM`` roles (analyze / plan / implement / review_solid /
reflect) on top of the shared, SSO-compatible Copilot plumbing in
:mod:`workflows.llm.copilot`. All orchestration LLM calls therefore route
through GitHub Copilot's OpenAI-compatible API.
"""

from __future__ import annotations

from workflows.llm.copilot import (  # re-exported for convenience
    CopilotAuthError,
    CopilotChatFactory,
    GitHubCopilotTokenProvider,
    StaticTokenProvider,
    TokenProvider,
)

__all__ = [
    "CopilotAuthError",
    "GitHubCopilotTokenProvider",
    "StaticTokenProvider",
    "TokenProvider",
    "GitHubCopilotLLM",
]

_SYSTEM = (
    "You are a senior PHP engineer modernizing a legacy Yii 1.1 application to "
    "run on PHP 8.4 while enforcing SOLID principles. Yii 1.1 pitfalls on PHP "
    "8.4 you must respect: each() is removed; dynamic properties are deprecated "
    "(use #[AllowDynamicProperties] on CComponent/CActiveRecord subclasses or "
    "declare properties); create_function is gone; curly-brace string offsets "
    "are removed; watch magic __get/__set on CActiveRecord. Prefer constructor "
    "dependency injection, single-responsibility classes, and interfaces over "
    "concrete coupling. You propose changes; deterministic tools (Rector, "
    "PHPStan, PHPUnit) verify them."
)


def _lessons_block(lessons) -> str:
    if not lessons:
        return "None."
    return "\n".join(f"- {le.title}: {le.detail}" for le in lessons)


class GitHubCopilotLLM:
    """DevLLM backed by GitHub Copilot's OpenAI-compatible chat API."""

    def __init__(
        self,
        *,
        token_provider: TokenProvider,
        model: str = "gpt-4o",
        base_url: str = "https://api.githubcopilot.com",
        editor_version: str = "vscode/1.95.0",
        integration_id: str = "vscode-chat",
        temperature: float = 0.0,
    ):
        self._factory = CopilotChatFactory(
            token_provider=token_provider,
            model=model,
            base_url=base_url,
            editor_version=editor_version,
            integration_id=integration_id,
            temperature=temperature,
        )

    def _structured(self, schema, human: str):
        messages = [("system", _SYSTEM), ("human", human)]
        result = self._factory.chat().with_structured_output(schema).invoke(messages)
        return result if isinstance(result, schema) else schema.model_validate(result)

    def analyze(self, *, goal, lessons, file_hints):
        from workflows.dev_orchestrator.schemas import AnalysisOutput

        human = (
            f"Goal: {goal}\n\n"
            f"Candidate files (may be empty): {file_hints or 'unknown'}\n\n"
            f"Relevant lessons from past work:\n{_lessons_block(lessons)}\n\n"
            "Identify the concrete target files to change and the PHP 8.4 / SOLID "
            "risks to watch for."
        )
        return self._structured(AnalysisOutput, human)

    def plan(self, *, goal, analysis, lessons):
        from workflows.dev_orchestrator.schemas import PlanOutput

        human = (
            f"Goal: {goal}\n\n"
            f"Target files: {analysis.target_files}\n"
            f"Known risks: {analysis.risks}\n\n"
            f"Relevant lessons:\n{_lessons_block(lessons)}\n\n"
            "Produce an ordered plan of 3-6 steps to make the change PHP 8.4 "
            "compatible and SOLID-compliant."
        )
        return self._structured(PlanOutput, human)

    def implement(self, *, goal, plan, reflections, lessons):
        from workflows.dev_orchestrator.schemas import ImplementOutput

        reflection_block = "\n".join(f"- {r}" for r in reflections) if reflections else "None."
        human = (
            f"Goal: {goal}\n\n"
            f"Plan steps: {[s.model_dump() for s in plan.steps]}\n\n"
            f"Prior failed-attempt reflections to fix this time:\n{reflection_block}\n\n"
            f"Relevant lessons:\n{_lessons_block(lessons)}\n\n"
            "Return a unified diff implementing the plan, the files it touches, "
            "and a one-line summary."
        )
        return self._structured(ImplementOutput, human)

    def review_solid(self, *, diff):
        from workflows.dev_orchestrator.schemas import SolidReview

        human = (
            "Review this unified diff strictly for SOLID violations "
            "(SRP, OCP, LSP, ISP, DIP). Report each violation with its principle "
            f"and file, and an overall score in [0,1].\n\nDiff:\n{diff}"
        )
        return self._structured(SolidReview, human)

    def reflect(self, *, goal, verify_report):
        from workflows.dev_orchestrator.schemas import Lesson

        human = (
            f"Goal: {goal}\n\n"
            f"The verification gates reported:\n{verify_report}\n\n"
            "Write ONE concise, reusable lesson that would prevent this failure "
            "next time. Give it a short title, a detail, and tags."
        )
        return self._structured(Lesson, human)
