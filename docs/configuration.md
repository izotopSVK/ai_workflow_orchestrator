# Configuration

## MVP API — environment variables

Loaded by `app/settings.py` (pydantic-settings) from the environment / `.env`.

| Var | Default | Purpose |
|-----|---------|---------|
| `DB_URL` | `postgresql+psycopg://workflow:workflow@localhost:5432/ai_workflows` | SQLAlchemy URL for app tables |
| `CHECKPOINT_DB_URL` | libpq URL to the same DB | LangGraph PostgresSaver checkpoints |
| `LLM_PROVIDER` | `github_copilot` | `github_copilot` or `fake` |
| `COPILOT_MODEL` | `chatgpt-5.6-terra` | planner model (variants `-sol` / `-terra` / `-luna`) |
| `COPILOT_BASE_URL` | `https://api.githubcopilot.com` | Copilot OpenAI-compatible API |
| `GH_COPILOT_OAUTH_TOKEN` | _(unset)_ | SSO-authorized GitHub OAuth token; else device flow |
| `COMPRESSOR` | `none` | `none` or `headroom` (context compression) |
| `HEADROOM_PROXY_URL` | _(unset)_ | proxy mode; overrides `COPILOT_BASE_URL` |
| `LLM_CACHE` | `none` | `none` / `memory` / `sqlite` (dedupe identical calls) |
| `ARTIFACT_DIR` | `./artifacts` | local artifact store path |

## Dev orchestrator — `DevOrchestratorConfig`

Constructed programmatically (a dataclass in
`workflows/dev_orchestrator/config.py`).

| Field | Default | Purpose |
|-------|---------|---------|
| `target_repo_path` | `None` | path to the legacy Yii 1.1 checkout (required for real runs) |
| `base_ref` | `"HEAD"` | ref each task worktree branches from |
| `branch_prefix` | `"task/"` | prefix for per-task branches |
| `copy_globs` | `config/*-local.php`, `.env` | files copied into each worktree |
| `symlink_map` | `vendor`, `runtime`, `assets`, `uploads` | dirs symlinked into each worktree |
| `rector_sets` | `PHP_84`, `CODE_QUALITY`, `DEAD_CODE` | Rector rule sets |
| `phpstan_level` | `"5"` | PHPStan level |
| `max_iterations` | `4` | Reflexion retry bound |
| `max_tool_steps` | `6` | max MCP tool-call rounds per implement step |
| `max_llm_calls` | `50` | budget: hard cap on total LLM calls per run (0 = unlimited) |
| `max_runtime_seconds` | `1800` | budget: wall-clock cap per run (0 = unlimited) |
| `require_human_review` | `True` | pause for approval before finalize |
| `retrieval_k` | `5` | lessons/skills pulled into a run |
| `copilot_model` | `chatgpt-5.6-terra` | default agent model |
| `agent_models` | `{}` | per-agent model overrides (see below) |
| `compressor` | `"none"` | `none` / `headroom` |
| `headroom_proxy_url` | `None` | Headroom proxy URL (overrides base_url) |
| `llm_cache` | `"none"` | `none` / `memory` / `sqlite` |
| `copilot_oauth_client_id` | Copilot editor app id | override with your org's OAuth app |

### Per-agent models

Each agent (`analyze`, `plan`, `implement`, `review_solid`, `reflect`) can run on
its own model; unlisted roles fall back to `copilot_model`.

```python
DevOrchestratorConfig(agent_models={
    "implement": "chatgpt-5.6-sol",
    "review_solid": "chatgpt-5.6-luna",
})
```

From an env string: `parse_agent_models("implement=chatgpt-5.6-sol,reflect=chatgpt-5.6-luna")`.

See [dev_orchestrator.md](dev_orchestrator.md) for the full model.
