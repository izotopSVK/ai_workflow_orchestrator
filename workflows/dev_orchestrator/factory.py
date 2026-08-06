from __future__ import annotations

from workflows.dev_orchestrator.config import DevOrchestratorConfig
from workflows.dev_orchestrator.deps import DevOrchestratorDeps
from workflows.dev_orchestrator.llm import FakeDevLLM, OllamaDevLLM
from workflows.dev_orchestrator.tools.memory import InMemoryMemoryStore
from workflows.dev_orchestrator.tools.php_toolchain import (
    FakePhpToolchain,
    SubprocessPhpToolchain,
)
from workflows.dev_orchestrator.tools.workspace import (
    FakeWorkspaceManager,
    GitWorktreeManager,
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


def build_real_deps(config: DevOrchestratorConfig) -> DevOrchestratorDeps:
    """Production dependency set. Requires ``config.target_repo_path`` to be set.

    Memory still uses the in-memory store until pgvector + embeddings are wired
    up (see :class:`PgVectorMemoryStore`).
    """
    if not config.target_repo_path:
        raise ValueError("config.target_repo_path must point at the legacy Yii 1.1 repo")
    return DevOrchestratorDeps(
        llm=OllamaDevLLM(model="qwen3.6", base_url="http://localhost:11434"),
        workspace=GitWorktreeManager(repo_path=config.target_repo_path),
        php=SubprocessPhpToolchain(),
        memory=InMemoryMemoryStore(),
        config=config,
    )
