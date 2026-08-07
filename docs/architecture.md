# Architecture

Two independent LangGraph pipelines share one set of building blocks. The guiding
principle everywhere: **the LLM is one node, never the engine.** The graph is the
engine; deterministic tools decide correctness; every side effect is a `Protocol`
with a Fake, so the whole system runs in tests without external services.

## MVP workflow graph

```
FastAPI ─▶ WorkflowService ─▶ LangGraph (plan → verify → human_review → finalize)
                                   │
                                   ├─▶ GitHub Copilot (enterprise LLM, SSO)
                                   ├─▶ PostgresSaver (graph checkpoints)
                                   └─▶ SQLAlchemy ORM (workflows, approvals, events, artifacts)
```

Durable resume via LangGraph's Postgres checkpointer keyed by `workflow_id`.

## Dev orchestrator (self-learning, Yii 1.1 → PHP 8.4)

```
START → bootstrap → load_context → retrieve → analyze → plan → implement → verify
  verify --ok--> human_review --approved--> finalize → learn → teardown → END
  verify --red,budget-left--> reflect → implement        (Reflexion retry loop)
  verify --red,exhausted--> finalize (failure)
  human_review --parked--> END (resume later)
```

| Stage | Role |
|-------|------|
| `bootstrap` | isolated git worktree: copy per-task config, symlink heavy dirs |
| `load_context` | load AGENTS.md/skills from the worktree |
| `retrieve` | pull relevant lessons from long-term memory (self-learning / RAG) |
| `analyze`→`plan`→`implement` | LLM agents produce target files, a plan, a diff |
| `verify` | php -l · Rector · PHPStan · PHP-CS-Fixer · PHPUnit · SOLID review |
| `reflect` | turn a failed gate into a lesson, retry (Reflexion) |
| `human_review` | pause for approval of the verified diff |
| `finalize` → `learn` → `teardown` | commit, distil lessons + reward, release worktree |

Full detail: [dev_orchestrator.md](dev_orchestrator.md).

## Dependency injection (SOLID)

Every side effect is an interface with a Fake (tests) and a real impl (prod):

| Interface | Fake | Real |
|-----------|------|------|
| `WorkflowLLM` / `DevLLM` | `Fake*LLM` | `CopilotWorkflowLLM` / `GitHubCopilotLLM` |
| `TokenProvider` | `StaticTokenProvider` | `GitHubCopilotTokenProvider` (SSO) |
| `ContextCompressor` | `NoOpCompressor` | `HeadroomCompressor` |
| `WorkspaceManager` | `FakeWorkspaceManager` | `GitWorktreeManager` |
| `PhpToolchain` | `FakePhpToolchain` | `SubprocessPhpToolchain` |
| `MemoryStore` | `InMemoryMemoryStore` | `PgVectorMemoryStore` *(stub)* |
| `InstructionsProvider` / `SkillLibrary` | `No*` / `Empty*` | `RepoInstructionsProvider` / `DirectorySkillLibrary` |
| `MCPToolProvider` | `No*` / `FakeMCPToolProvider` | `MultiServerMCPToolProvider` |

## Cross-cutting

- **Enterprise LLM (Copilot + SSO):** [auth_and_security.md](auth_and_security.md)
- **Secret/PII redaction:** [logging_security.md](logging_security.md)
- **Token compression (Headroom/RTK):** [headroom_integration.md](headroom_integration.md)
- **AGENTS.md & skills:** [agents_and_skills.md](agents_and_skills.md)
- **MCP client (external tools):** [mcp.md](mcp.md)

## Project layout

```
app/                      FastAPI app: main.py, settings.py, api/routes.py
workflows/
  graph/                  MVP graph: builder, state, deps, routing
  nodes/                  MVP nodes: plan, verify, human_review, finalize
  services/               WorkflowService, ApprovalService, Event/Artifact services
  persistence/            SQLAlchemy ORM, repositories, db engine
  models/                 pydantic schemas, enums
  llm/                    factory (WorkflowLLM), copilot (SSO auth+chat), compression, cache
  observability/          redaction (secrets/PII)
  dev_orchestrator/       self-learning pipeline:
    builder, state, deps, config, service, factory, schemas
    dev_llm (Copilot transport), prompts, instructions, skills, text,
    mcp_tools (MCP client), tool_loop (function-calling loop)
    nodes/                _helpers (advance, context_from_state), bootstrap,
                          load_context, retrieve, analyze, plan, implement,
                          verify, reflect, human_review, finalize, learn, teardown
    tools/                workspace (git worktree), php_toolchain, memory
alembic/                  DB migrations
tests/                    pytest suite (Fakes; no external services)
docs/                     this documentation
```
