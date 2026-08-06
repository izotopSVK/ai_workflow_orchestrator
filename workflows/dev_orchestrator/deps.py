from __future__ import annotations

from dataclasses import dataclass

from workflows.dev_orchestrator.config import DevOrchestratorConfig
from workflows.dev_orchestrator.llm import DevLLM
from workflows.dev_orchestrator.tools.memory import MemoryStore
from workflows.dev_orchestrator.tools.php_toolchain import PhpToolchain
from workflows.dev_orchestrator.tools.workspace import WorkspaceManager


@dataclass
class DevOrchestratorDeps:
    """Runtime dependencies injected into graph nodes via closures.

    Every field is an interface (Protocol), so tests inject Fakes and prod
    injects git/PHP/pgvector/Ollama-backed implementations without touching the
    graph or nodes.
    """

    llm: DevLLM
    workspace: WorkspaceManager
    php: PhpToolchain
    memory: MemoryStore
    config: DevOrchestratorConfig
