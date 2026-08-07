from __future__ import annotations

from dataclasses import dataclass

from workflows.dev_orchestrator.config import DevOrchestratorConfig
from workflows.dev_orchestrator.instructions import InstructionsProvider
from workflows.dev_orchestrator.llm import DevLLM
from workflows.dev_orchestrator.skills import SkillLibrary
from workflows.dev_orchestrator.tools.memory import MemoryStore
from workflows.dev_orchestrator.tools.php_toolchain import PhpToolchain
from workflows.dev_orchestrator.tools.workspace import WorkspaceManager


@dataclass
class DevOrchestratorDeps:
    """Runtime dependencies injected into graph nodes via closures.

    Every field is an interface (Protocol), so tests inject Fakes and prod
    injects git/PHP/pgvector/Copilot-backed implementations without touching the
    graph or nodes.
    """

    llm: DevLLM
    workspace: WorkspaceManager
    php: PhpToolchain
    memory: MemoryStore
    config: DevOrchestratorConfig
    # AGENTS.md-style project instructions + skills loaded from the target repo.
    # Optional (default None -> No/Empty providers) so existing wiring keeps working.
    instructions: InstructionsProvider | None = None
    skills: SkillLibrary | None = None
