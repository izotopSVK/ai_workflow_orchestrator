"""GitHub Copilot DevLLM for the self-learning dev orchestrator.

Implements the ``DevLLM`` roles (analyze / plan / implement / review_solid /
reflect) on top of the shared, SSO-compatible Copilot plumbing in
:mod:`workflows.llm.copilot`. All orchestration LLM calls therefore route
through GitHub Copilot's OpenAI-compatible API.
"""

from __future__ import annotations

from workflows.llm.compression import ContextCompressor, NoOpCompressor
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


# The orchestrator's "agents" — each is an LLM role that can run on its own
# Copilot model, configured independently.
AGENT_ROLES = ("analyze", "plan", "implement", "review_solid", "reflect")


class GitHubCopilotLLM:
    """DevLLM backed by GitHub Copilot's OpenAI-compatible chat API.

    Each agent role can use a different Copilot model via ``role_models`` (falling
    back to ``model``). One ``CopilotChatFactory`` is built per distinct model and
    they all share the same ``token_provider``, so a single SSO login serves every
    agent regardless of how many models are in play.
    """

    def __init__(
        self,
        *,
        token_provider: TokenProvider,
        model: str = "chatgpt-5.6-terra",
        role_models: dict[str, str] | None = None,
        base_url: str = "https://api.githubcopilot.com",
        editor_version: str = "vscode/1.95.0",
        integration_id: str = "vscode-chat",
        temperature: float = 0.0,
        compressor: ContextCompressor | None = None,
    ):
        self._token_provider = token_provider
        self._default_model = model
        self._role_models = dict(role_models or {})
        self._base_url = base_url
        self._editor_version = editor_version
        self._integration_id = integration_id
        self._temperature = temperature
        self._compressor = compressor or NoOpCompressor()
        self._factories: dict[str, CopilotChatFactory] = {}

    def model_for(self, role: str) -> str:
        """The Copilot model this agent role runs on."""
        return self._role_models.get(role, self._default_model)

    def _factory_for(self, role: str) -> CopilotChatFactory:
        model = self.model_for(role)
        factory = self._factories.get(model)
        if factory is None:
            factory = CopilotChatFactory(
                token_provider=self._token_provider,
                model=model,
                base_url=self._base_url,
                editor_version=self._editor_version,
                integration_id=self._integration_id,
                temperature=self._temperature,
            )
            self._factories[model] = factory
        return factory

    def _system(self, system_extra: str) -> str:
        if not system_extra:
            return _SYSTEM
        return f"{_SYSTEM}\n\n# Project instructions & skills (from the target repo)\n{system_extra}"

    def prepare_messages(self, human: str, role: str, system_extra: str = "") -> list[tuple[str, str]]:
        """Build and compress the messages for a role (seam for testing)."""
        messages = [("system", self._system(system_extra)), ("human", human)]
        return self._compressor.compress_messages(messages, model=self.model_for(role))

    def _structured(self, schema, human: str, role: str, system_extra: str = ""):
        messages = self.prepare_messages(human, role, system_extra)
        result = self._factory_for(role).chat().with_structured_output(schema).invoke(messages)
        return result if isinstance(result, schema) else schema.model_validate(result)

    def analyze(self, *, goal, lessons, file_hints, system_extra=""):
        from workflows.dev_orchestrator.schemas import AnalysisOutput

        human = (
            f"Goal: {goal}\n\n"
            f"Candidate files (may be empty): {file_hints or 'unknown'}\n\n"
            f"Relevant lessons from past work:\n{_lessons_block(lessons)}\n\n"
            "Identify the concrete target files to change and the PHP 8.4 / SOLID "
            "risks to watch for."
        )
        return self._structured(AnalysisOutput, human, "analyze", system_extra)

    def plan(self, *, goal, analysis, lessons, system_extra=""):
        from workflows.dev_orchestrator.schemas import PlanOutput

        human = (
            f"Goal: {goal}\n\n"
            f"Target files: {analysis.target_files}\n"
            f"Known risks: {analysis.risks}\n\n"
            f"Relevant lessons:\n{_lessons_block(lessons)}\n\n"
            "Produce an ordered plan of 3-6 steps to make the change PHP 8.4 "
            "compatible and SOLID-compliant."
        )
        return self._structured(PlanOutput, human, "plan", system_extra)

    def implement(self, *, goal, plan, reflections, lessons, system_extra=""):
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
        return self._structured(ImplementOutput, human, "implement", system_extra)

    def review_solid(self, *, diff, system_extra=""):
        from workflows.dev_orchestrator.schemas import SolidReview

        human = (
            "Review this unified diff strictly for SOLID violations "
            "(SRP, OCP, LSP, ISP, DIP). Report each violation with its principle "
            f"and file, and an overall score in [0,1].\n\nDiff:\n{diff}"
        )
        return self._structured(SolidReview, human, "review_solid", system_extra)

    def reflect(self, *, goal, verify_report, system_extra=""):
        from workflows.dev_orchestrator.schemas import Lesson

        human = (
            f"Goal: {goal}\n\n"
            f"The verification gates reported:\n{verify_report}\n\n"
            "Write ONE concise, reusable lesson that would prevent this failure "
            "next time. Give it a short title, a detail, and tags."
        )
        return self._structured(Lesson, human, "reflect", system_extra)
