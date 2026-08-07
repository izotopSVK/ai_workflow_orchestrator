# Usage

Two independent systems live in this repo. Pick the one you need.

- **MVP workflow API** — a generic plan → verify → human-approval → finalize
  workflow, exposed over HTTP.
- **Dev orchestrator** — the self-learning Yii 1.1 → PHP 8.4 pipeline, used
  programmatically.

---

## MVP workflow API

Start the server (requires Postgres + `alembic upgrade head`, see
[installation.md](installation.md)):

```bash
uvicorn app.main:app --reload
```

### Endpoints

| Method & path | Purpose |
|---------------|---------|
| `POST /workflows` | Start a workflow (`{"goal": "..."}`) — runs to the human-review pause |
| `GET /workflows/{id}` | Inspect status, plan, completed steps, result |
| `POST /workflows/{id}/resume` | Resume a paused workflow |
| `POST /approvals/{approval_id}/approve` | Approve the pending review and resume to finalize |

### Example flow

```bash
# 1. start — runs plan → verify → human_review, then pauses
curl -X POST localhost:8000/workflows \
  -H 'content-type: application/json' \
  -d '{"goal": "Draft a status report"}'
# → {"workflow_id": "...", "status": "waiting_for_human", "pending_approval_id": "..."}

# 2. inspect
curl localhost:8000/workflows/<workflow_id>

# 3. approve → resumes to finalize
curl -X POST localhost:8000/approvals/<approval_id>/approve

# 4. confirm completion
curl localhost:8000/workflows/<workflow_id>
# → {"status": "completed", "final_result": {...}}
```

Durable resume is backed by LangGraph's Postgres checkpointer keyed by
`workflow_id`, so a restart mid-run continues where it left off.

---

## Dev orchestrator (Yii 1.1 → PHP 8.4)

Run it programmatically. With Fakes it needs nothing installed; for real work set
`config.target_repo_path` and provide Copilot auth.

### Offline / demo (Fakes)

```python
from langgraph.checkpoint.memory import InMemorySaver
from workflows.dev_orchestrator.builder import build_dev_orchestrator_graph
from workflows.dev_orchestrator.config import DevOrchestratorConfig
from workflows.dev_orchestrator.factory import build_fake_deps
from workflows.dev_orchestrator.service import DevOrchestratorService

config = DevOrchestratorConfig(require_human_review=True)
graph = build_dev_orchestrator_graph(checkpointer=InMemorySaver(), deps=build_fake_deps(config))
service = DevOrchestratorService(graph=graph, config=config)

parked = service.start(goal="Migrate User model to PHP 8.4")   # runs to human_review
done = service.approve(parked["workflow_id"])                  # resumes to completion
print(done["status"], done["final_result"])
```

### Real run (Copilot + git worktree + PHP tools)

```python
from langgraph.checkpoint.memory import InMemorySaver
from workflows.dev_orchestrator.builder import build_dev_orchestrator_graph
from workflows.dev_orchestrator.config import DevOrchestratorConfig
from workflows.dev_orchestrator.factory import build_real_deps
from workflows.dev_orchestrator.service import DevOrchestratorService

config = DevOrchestratorConfig(
    target_repo_path="/path/to/legacy-yii-app",   # required
    base_ref="origin/main",
    require_human_review=True,
    # per-agent models (any role omitted falls back to copilot_model):
    agent_models={"implement": "chatgpt-5.6-sol", "review_solid": "chatgpt-5.6-luna"},
    # optional Headroom compression + response cache:
    compressor="headroom", llm_cache="memory",
)
deps = build_real_deps(config)   # reads GH_COPILOT_OAUTH_TOKEN for Copilot auth
graph = build_dev_orchestrator_graph(checkpointer=InMemorySaver(), deps=deps)
service = DevOrchestratorService(graph=graph, config=config)

state = service.start(goal="Make protected/models/User.php PHP 8.4 compatible")
```

What a run does: creates an isolated **git worktree** (copies per-task config,
symlinks `vendor/`/`runtime/`), loads **AGENTS.md/skills**, retrieves **lessons**
from memory, plans and implements a diff, **verifies** it (php -l · Rector ·
PHPStan · PHP-CS-Fixer · PHPUnit · SOLID), **reflects** and retries on failure,
pauses for human review, commits, distils lessons back into memory, and tears the
worktree down.

### Customize per target repo

- **Per-agent models:** [dev_orchestrator.md](dev_orchestrator.md#per-agent-models)
- **AGENTS.md / skills:** drop `AGENTS.md`/`CLAUDE.md` and `.claude/skills/*.md`
  in the target repo — see [agents_and_skills.md](agents_and_skills.md)
- **Token compression (Headroom/RTK):** [headroom_integration.md](headroom_integration.md)

---

## Running tests

```bash
pytest -q            # whole suite (Fakes; no external services)
pytest tests/test_dev_orchestrator.py -q
```
