from __future__ import annotations

from typing import Protocol

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


class OllamaWorkflowLLM:
    """Real LLM backed by a local Ollama server via langchain-ollama."""

    def __init__(self, *, model: str, base_url: str):
        from langchain_ollama import ChatOllama

        self._chat = ChatOllama(model=model, base_url=base_url, temperature=0.0)

    def generate_plan(self, goal: str) -> PlanOutput:
        prompt = (
            "You are a workflow planner. Given a goal, return a structured plan "
            "with 3-6 ordered steps. Each step has an id, a short description, "
            "and the expected output.\n\n"
            f"Goal:\n{goal}"
        )
        structured = self._chat.with_structured_output(PlanOutput)
        result = structured.invoke(prompt)
        if isinstance(result, PlanOutput):
            return result
        return PlanOutput.model_validate(result)


def build_llm(provider: str, *, ollama_model: str, ollama_base_url: str) -> WorkflowLLM:
    provider = provider.lower()
    if provider == "fake":
        return FakeWorkflowLLM()
    if provider == "ollama":
        return OllamaWorkflowLLM(model=ollama_model, base_url=ollama_base_url)
    raise ValueError(f"Unknown LLM_PROVIDER: {provider!r}")
