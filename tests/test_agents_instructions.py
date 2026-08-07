from __future__ import annotations

from langgraph.checkpoint.memory import InMemorySaver

from workflows.dev_orchestrator.builder import build_dev_orchestrator_graph
from workflows.dev_orchestrator.config import DevOrchestratorConfig
from workflows.dev_orchestrator.dev_llm import GitHubCopilotLLM, StaticTokenProvider
from workflows.dev_orchestrator.deps import DevOrchestratorDeps
from workflows.dev_orchestrator.instructions import (
    NoInstructionsProvider,
    RepoInstructionsProvider,
)
from workflows.dev_orchestrator.llm import FakeDevLLM
from workflows.dev_orchestrator.nodes.load_context import make_load_context_node
from workflows.dev_orchestrator.service import DevOrchestratorService
from workflows.dev_orchestrator.skills import (
    DirectorySkillLibrary,
    EmptySkillLibrary,
)
from workflows.dev_orchestrator.tools.memory import InMemoryMemoryStore
from workflows.dev_orchestrator.tools.php_toolchain import FakePhpToolchain
from workflows.dev_orchestrator.tools.workspace import FakeWorkspaceManager


# --- instructions loading (AGENTS.md standard) ------------------------------

def test_loads_agents_md_and_claude_md(tmp_path):
    (tmp_path / "AGENTS.md").write_text("Always run composer test before committing.")
    (tmp_path / "CLAUDE.md").write_text("Use PSR-12 formatting.")
    (tmp_path / ".github").mkdir()
    (tmp_path / ".github" / "copilot-instructions.md").write_text("Prefer typed properties.")

    text = RepoInstructionsProvider().load(str(tmp_path))

    assert "composer test" in text
    assert "PSR-12" in text
    assert "typed properties" in text
    assert "From AGENTS.md" in text  # provenance header


def test_no_instructions_when_absent(tmp_path):
    assert RepoInstructionsProvider().load(str(tmp_path)) == ""
    assert NoInstructionsProvider().load(str(tmp_path)) == ""


def test_nested_agents_md_for_paths(tmp_path):
    (tmp_path / "AGENTS.md").write_text("Root rules.")
    sub = tmp_path / "protected" / "models"
    sub.mkdir(parents=True)
    (sub / "AGENTS.md").write_text("Models must declare properties explicitly.")

    text = RepoInstructionsProvider().load_for_paths(
        str(tmp_path), ["protected/models/User.php"]
    )
    assert "Root rules." in text
    assert "declare properties explicitly" in text


# --- skills -----------------------------------------------------------------

def _write_skill(root, rel, name, description, body):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\nname: {name}\ndescription: {description}\n---\n{body}")


def test_directory_skill_library_loads_and_selects(tmp_path):
    _write_skill(tmp_path, ".claude/skills/migrate.md", "Yii Migration",
                 "How to migrate Yii models to PHP 8.4", "Step 1: run Rector...")
    _write_skill(tmp_path, "skills/deploy.md", "Deploy",
                 "How to deploy the app", "Step 1: build...")

    lib = DirectorySkillLibrary()
    all_skills = lib.load(str(tmp_path))
    assert {s.name for s in all_skills} == {"Yii Migration", "Deploy"}

    selected = lib.select(str(tmp_path), "migrate Yii model to php", k=5)
    assert [s.name for s in selected] == ["Yii Migration"]


def test_empty_skill_library(tmp_path):
    assert EmptySkillLibrary().select(str(tmp_path), "anything", 5) == []


# --- load_context node -------------------------------------------------------

def test_load_context_node_composes_agent_instructions(tmp_path):
    (tmp_path / "AGENTS.md").write_text("Follow SOLID strictly.")
    _write_skill(tmp_path, ".claude/skills/migrate.md", "Migration",
                 "migrate Yii to php 8.4", "Run Rector then PHPStan.")

    deps = DevOrchestratorDeps(
        llm=FakeDevLLM(),
        workspace=FakeWorkspaceManager(),
        php=FakePhpToolchain(),
        memory=InMemoryMemoryStore(),
        config=DevOrchestratorConfig(),
        instructions=RepoInstructionsProvider(),
        skills=DirectorySkillLibrary(),
    )
    node = make_load_context_node(deps)
    out = node({"goal": "migrate Yii model to php 8.4", "workspace": {"path": str(tmp_path)}})

    assert "Follow SOLID strictly." in out["agent_instructions"]
    assert "Run Rector then PHPStan." in out["agent_instructions"]
    assert out["selected_skills"][0]["name"] == "Migration"
    assert "load_context" in out["completed_steps"]


def test_load_context_graceful_without_providers():
    # No providers wired (None) -> empty instructions, no crash.
    deps = DevOrchestratorDeps(
        llm=FakeDevLLM(),
        workspace=FakeWorkspaceManager(),
        php=FakePhpToolchain(),
        memory=InMemoryMemoryStore(),
        config=DevOrchestratorConfig(),
    )
    node = make_load_context_node(deps)
    out = node({"goal": "x", "workspace": {"path": "/nonexistent"}})
    assert out["agent_instructions"] == ""
    assert out["selected_skills"] == []


# --- instructions reach the agent prompt ------------------------------------

def test_instructions_injected_into_system_prompt():
    llm = GitHubCopilotLLM(token_provider=StaticTokenProvider("t"))
    messages = llm.prepare_messages("do it", "implement", instructions="PROJECT RULE: X")
    system = messages[0][1]
    assert "PROJECT RULE: X" in system
    assert "senior PHP engineer" in system  # base system prompt still present


# --- end-to-end still works with context loading ----------------------------

def test_graph_runs_with_load_context(tmp_path):
    (tmp_path / "AGENTS.md").write_text("Be careful.")
    config = DevOrchestratorConfig(require_human_review=False)
    # Point the fake workspace so the worktree path is a real dir with AGENTS.md.
    ws = FakeWorkspaceManager(root=str(tmp_path))
    deps = DevOrchestratorDeps(
        llm=FakeDevLLM(),
        workspace=ws,
        php=FakePhpToolchain(),
        memory=InMemoryMemoryStore(),
        config=config,
        instructions=RepoInstructionsProvider(),
        skills=DirectorySkillLibrary(),
    )
    graph = build_dev_orchestrator_graph(checkpointer=InMemorySaver(), deps=deps)
    service = DevOrchestratorService(graph=graph, config=config)
    state = service.start(goal="Migrate models")
    assert state["status"] == "completed"
    assert "load_context" in state["completed_steps"]
