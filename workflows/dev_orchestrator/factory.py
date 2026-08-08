from __future__ import annotations

from workflows.dev_orchestrator.config import DevOrchestratorConfig
from workflows.dev_orchestrator.dev_llm import (
    GitHubCopilotLLM,
    GitHubCopilotTokenProvider,
    TokenProvider,
)
from workflows.dev_orchestrator.deps import DevOrchestratorDeps
from workflows.dev_orchestrator.instructions import RepoInstructionsProvider
from workflows.dev_orchestrator.llm import DevLLM, FakeDevLLM
from workflows.dev_orchestrator.mcp_tools import (
    MCPToolProvider,
    MultiServerMCPToolProvider,
    NoMCPToolProvider,
)
from workflows.dev_orchestrator.embeddings import EmbeddingProvider, OpenAIEmbeddingProvider
from workflows.dev_orchestrator.skills import DirectorySkillLibrary
from workflows.llm.cache import configure_llm_cache
from workflows.llm.compression import build_compressor
from workflows.dev_orchestrator.tools.memory import (
    InMemoryMemoryStore,
    MemoryStore,
    SqlAlchemyMemoryStore,
)
from workflows.dev_orchestrator.tools.php_toolchain import (
    FakePhpToolchain,
    SubprocessPhpToolchain,
)
from workflows.dev_orchestrator.tools.workspace import (
    FakeWorkspaceManager,
    GitWorktreeManager,
)


def build_copilot_llm(
    config: DevOrchestratorConfig,
    *,
    token_provider: TokenProvider | None = None,
) -> DevLLM:
    """Build the GitHub Copilot (SSO-compatible) DevLLM from config.

    ``token_provider`` can be injected (e.g. a pre-authorized token in CI);
    otherwise a :class:`GitHubCopilotTokenProvider` runs the OAuth device flow /
    reads ``GH_COPILOT_OAUTH_TOKEN`` and refreshes short-lived Copilot tokens.
    """
    provider = token_provider or GitHubCopilotTokenProvider(
        client_id=config.copilot_oauth_client_id,
        editor_version=config.copilot_editor_version,
        integration_id=config.copilot_integration_id,
    )
    # Response cache to dedupe identical Copilot calls (process-global).
    configure_llm_cache(config.llm_cache)
    # Proxy mode: route through the Headroom proxy if configured.
    base_url = config.headroom_proxy_url or config.copilot_base_url
    compressor = build_compressor(config.compressor, model=config.copilot_model)
    return GitHubCopilotLLM(
        token_provider=provider,
        model=config.copilot_model,
        role_models=config.agent_models,
        base_url=base_url,
        editor_version=config.copilot_editor_version,
        integration_id=config.copilot_integration_id,
        compressor=compressor,
        max_tool_steps=config.max_tool_steps,
    )


def build_mcp_provider(config: DevOrchestratorConfig) -> MCPToolProvider:
    """MCP client from config: connect to configured servers, else a no-op."""
    if config.mcp_servers:
        return MultiServerMCPToolProvider(config.mcp_servers)
    return NoMCPToolProvider()


def build_embedder(config: DevOrchestratorConfig) -> EmbeddingProvider:
    """Embedding provider for the persistent memory (OpenAI-compatible)."""
    return OpenAIEmbeddingProvider(
        model=config.embedding_model, base_url=config.embedding_base_url
    )


def build_memory(
    config: DevOrchestratorConfig, *, session_factory=None, embedder: EmbeddingProvider | None = None
) -> MemoryStore:
    """Persistent (sql) or ephemeral (in_memory) memory from config.

    'sql' requires a ``session_factory`` and uses embedding-based retrieval that
    survives restarts; otherwise the in-process store is used. ``embedder`` can be
    injected (tests); by default a real OpenAI-compatible embedder is built.
    """
    if config.memory_backend == "sql" and session_factory is not None:
        return SqlAlchemyMemoryStore(
            session_factory=session_factory,
            embedder=embedder or build_embedder(config),
        )
    return InMemoryMemoryStore()


def build_fake_deps(config: DevOrchestratorConfig | None = None) -> DevOrchestratorDeps:
    """All-Fake dependency set: runs the full graph with no git/PHP/LLM/Postgres."""
    return DevOrchestratorDeps(
        llm=FakeDevLLM(),
        workspace=FakeWorkspaceManager(),
        php=FakePhpToolchain(),
        memory=InMemoryMemoryStore(),
        config=config or DevOrchestratorConfig(),
    )


def build_real_deps(
    config: DevOrchestratorConfig,
    *,
    token_provider: TokenProvider | None = None,
    session_factory=None,
) -> DevOrchestratorDeps:
    """Production dependency set: GitHub Copilot LLM + git worktree + PHP tools.

    Requires ``config.target_repo_path``. With ``config.memory_backend == "sql"``
    and a ``session_factory``, long-term memory persists across restarts via
    embeddings; otherwise the in-memory store is used.
    """
    if not config.target_repo_path:
        raise ValueError("config.target_repo_path must point at the legacy Yii 1.1 repo")
    return DevOrchestratorDeps(
        llm=build_copilot_llm(config, token_provider=token_provider),
        workspace=GitWorktreeManager(repo_path=config.target_repo_path),
        php=SubprocessPhpToolchain(),
        memory=build_memory(config, session_factory=session_factory),
        config=config,
        instructions=RepoInstructionsProvider(),
        skills=DirectorySkillLibrary(),
        mcp=build_mcp_provider(config),
    )
