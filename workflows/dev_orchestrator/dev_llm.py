"""GitHub Copilot DevLLM for the self-learning dev orchestrator.

Thin transport: it turns a role + inputs into a compressed chat call against
GitHub Copilot's OpenAI-compatible API and parses the structured result. Prompt
wording lives in :mod:`workflows.dev_orchestrator.prompts`; SSO auth and chat
construction live in :mod:`workflows.llm.copilot`.

Each agent role may run on its own Copilot model (``role_models``); one chat
factory is built per distinct model and they share a single SSO token provider,
so mixing models costs one login.
"""

from __future__ import annotations

from collections.abc import Callable

from workflows.dev_orchestrator import prompts
from workflows.dev_orchestrator.mcp_tools import MCPToolResult, MCPToolSpec
from workflows.dev_orchestrator.schemas import (
    AnalysisOutput,
    ImplementOutput,
    Lesson,
    PlanOutput,
    PromptContext,
    SolidReview,
)
from workflows.dev_orchestrator.tool_loop import mcp_specs_to_openai_tools, run_tool_loop
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
    "AGENT_ROLES",
]

# The orchestrator's "agents" — each is an LLM role that can run on its own model.
AGENT_ROLES = ("analyze", "plan", "implement", "review_solid", "reflect")


class GitHubCopilotLLM:
    """DevLLM backed by GitHub Copilot's OpenAI-compatible chat API."""

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
        max_tool_steps: int = 6,
    ):
        self._token_provider = token_provider
        self._default_model = model
        self._role_models = dict(role_models or {})
        self._base_url = base_url
        self._editor_version = editor_version
        self._integration_id = integration_id
        self._temperature = temperature
        self._compressor = compressor or NoOpCompressor()
        self._max_tool_steps = max_tool_steps
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

    def prepare_messages(self, human: str, role: str, instructions: str = "") -> list[tuple[str, str]]:
        """Build and compress the messages for a role (seam for testing)."""
        messages = [("system", prompts.system_prompt(instructions)), ("human", human)]
        return self._compressor.compress_messages(messages, model=self.model_for(role))

    def _structured(self, schema, human: str, role: str, instructions: str = ""):
        messages = self.prepare_messages(human, role, instructions)
        result = self._factory_for(role).chat().with_structured_output(schema).invoke(messages)
        return result if isinstance(result, schema) else schema.model_validate(result)

    def analyze(self, *, goal: str, file_hints: list[str], ctx: PromptContext) -> AnalysisOutput:
        human = prompts.analyze_prompt(goal, file_hints, ctx)
        return self._structured(AnalysisOutput, human, "analyze", ctx.instructions)

    def plan(self, *, goal: str, analysis: AnalysisOutput, ctx: PromptContext) -> PlanOutput:
        human = prompts.plan_prompt(goal, analysis, ctx)
        return self._structured(PlanOutput, human, "plan", ctx.instructions)

    def implement(
        self,
        *,
        goal: str,
        plan: PlanOutput,
        ctx: PromptContext,
        tools: list[MCPToolSpec] | None = None,
        execute: Callable[[str, dict], MCPToolResult] | None = None,
    ) -> ImplementOutput:
        human = prompts.implement_prompt(goal, plan, ctx)

        # No MCP tools available -> single structured call (as before).
        if not tools or execute is None:
            return self._structured(ImplementOutput, human, "implement", ctx.instructions)

        # Function-calling loop: let the model call MCP tools, then coerce the
        # enriched conversation into the structured diff.
        base = self._factory_for("implement").chat()
        bound = base.bind_tools(mcp_specs_to_openai_tools(tools))
        messages = self.prepare_messages(human, "implement", ctx.instructions)
        loop = run_tool_loop(bound, messages, execute, max_steps=self._max_tool_steps)
        convo = loop.messages + [
            ("human", "Using any tool results above, return the final unified diff, "
                      "the files it touches, and a one-line summary."),
        ]
        result = base.with_structured_output(ImplementOutput).invoke(convo)
        return result if isinstance(result, ImplementOutput) else ImplementOutput.model_validate(result)

    def review_solid(self, *, diff: str, ctx: PromptContext) -> SolidReview:
        human = prompts.review_solid_prompt(diff)
        return self._structured(SolidReview, human, "review_solid", ctx.instructions)

    def reflect(self, *, goal: str, verify_report: dict, ctx: PromptContext) -> Lesson:
        human = prompts.reflect_prompt(goal, verify_report)
        return self._structured(Lesson, human, "reflect", ctx.instructions)
