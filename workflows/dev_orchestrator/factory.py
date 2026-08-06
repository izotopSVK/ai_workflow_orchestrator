from __future__ import annotations

from workflows.dev_orchestrator.config import DevOrchestratorConfig
from workflows.dev_orchestrator.copilot import (
    GitHubCopilotLLM,
    GitHubCopilotTokenProvider,
    TokenProvider,
)
from workflows.dev_orchestrator.deps import DevOrchestratorDeps
from workflows.dev_orchestrator.llm import DevLLM, FakeDevLLM
from workflows.dev_orchestrator.tools.memory import InMemoryMemoryStore
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
    return GitHubCopilotLLM(
        token_provider=provider,
        model=config.copilot_model,
        base_url=config.copilot_base_url,
        editor_version=config.copilot_editor_version,
        integration_id=config.copilot_integration_id,
    )


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
) -> DevOrchestratorDeps:
    """Production dependency set: GitHub Copilot LLM + git worktree + PHP tools.

    Requires ``config.target_repo_path``. Memory still uses the in-memory store
    until pgvector + embeddings are wired up (see :class:`PgVectorMemoryStore`).
    """
    if not config.target_repo_path:
        raise ValueError("config.target_repo_path must point at the legacy Yii 1.1 repo")
    return DevOrchestratorDeps(
        llm=build_copilot_llm(config, token_provider=token_provider),
        workspace=GitWorktreeManager(repo_path=config.target_repo_path),
        php=SubprocessPhpToolchain(),
        memory=InMemoryMemoryStore(),
        config=config,
    )
