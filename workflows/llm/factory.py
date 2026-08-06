from __future__ import annotations

from typing import Protocol

from workflows.llm.compression import ContextCompressor, NoOpCompressor
from workflows.models.schemas import PlanItem, PlanOutput


class WorkflowLLM(Protocol):
    def generate_plan(self, goal: str) -> PlanOutput: ...


class FakeWorkflowLLM:
    """Deterministic LLM used in tests and when no real provider is configured."""

    def generate_plan(self, goal: str) -> PlanOutput:
        return PlanOutput(
            steps=[
                PlanItem(
                    id="collect_data",
                    description=f"Collect required data for: {goal}",
                    expected_output="Structured input data",
                ),
                PlanItem(
                    id="process",
                    description="Process collected data",
                    expected_output="Processed result",
                ),
                PlanItem(
                    id="verify",
                    description="Verify result quality",
                    expected_output="Verification report",
                ),
                PlanItem(
                    id="finalize",
                    description="Produce final output",
                    expected_output="Final report",
                ),
            ],
            confidence=0.9,
        )


class CopilotWorkflowLLM:
    """Real LLM backed by GitHub Copilot (enterprise, SSO-compatible).

    Routes planning through Copilot's OpenAI-compatible API. The Copilot token is
    supplied by a :class:`TokenProvider`; by default a
    :class:`GitHubCopilotTokenProvider` handles the SSO device flow and token
    refresh.
    """

    def __init__(
        self,
        *,
        model: str,
        base_url: str,
        token_provider=None,
        compressor: ContextCompressor | None = None,
    ):
        from workflows.llm.copilot import CopilotChatFactory, GitHubCopilotTokenProvider

        self._model = model
        self._compressor = compressor or NoOpCompressor()
        self._factory = CopilotChatFactory(
            token_provider=token_provider or GitHubCopilotTokenProvider(),
            model=model,
            base_url=base_url,
        )

    def prepare_messages(self, goal: str) -> list[tuple[str, str]]:
        """Build and compress the planner messages (seam for testing)."""
        prompt = (
            "You are a workflow planner. Given a goal, return a structured plan "
            "with 3-6 ordered steps. Each step has an id, a short description, "
            "and the expected output.\n\n"
            f"Goal:\n{goal}"
        )
        messages = [("human", prompt)]
        return self._compressor.compress_messages(messages, model=self._model)

    def generate_plan(self, goal: str) -> PlanOutput:
        messages = self.prepare_messages(goal)
        structured = self._factory.chat().with_structured_output(PlanOutput)
        result = structured.invoke(messages)
        if isinstance(result, PlanOutput):
            return result
        return PlanOutput.model_validate(result)


def build_llm(
    provider: str,
    *,
    copilot_model: str = "chatgpt-5.6-terra",
    copilot_base_url: str = "https://api.githubcopilot.com",
    token_provider=None,
    compressor: str = "none",
    headroom_proxy_url: str | None = None,
    llm_cache: str = "none",
) -> WorkflowLLM:
    provider = provider.lower()
    if provider == "fake":
        return FakeWorkflowLLM()
    if provider in ("github_copilot", "copilot"):
        from workflows.llm.cache import configure_llm_cache
        from workflows.llm.compression import build_compressor

        configure_llm_cache(llm_cache)
        return CopilotWorkflowLLM(
            model=copilot_model,
            base_url=headroom_proxy_url or copilot_base_url,
            token_provider=token_provider,
            compressor=build_compressor(compressor, model=copilot_model),
        )
    raise ValueError(f"Unknown LLM_PROVIDER: {provider!r}")
