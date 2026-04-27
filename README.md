# AI Workflow Orchestrator

Python-native durable AI workflow system built on **LangGraph** (stateful graph execution + checkpointing), **LangChain** (LLM/tool abstractions), and **PostgreSQL** (application state + LangGraph checkpoints).

This repo implements the MVP slice: a workflow graph that plans, verifies, pauses for human approval, and finalizes — with durable resume via LangGraph's Postgres checkpointer.

## Architecture (MVP)

```
FastAPI ─▶ WorkflowService ─▶ LangGraph (plan → verify → human_review → finalize)
                                   │
                                   ├─▶ ChatOllama (local LLM, qwen3.6 by default)
                                   ├─▶ PostgresSaver (graph checkpoints)
                                   └─▶ SQLAlchemy ORM (workflows, approvals, events, artifacts, ...)
```

The LLM is one node inside the graph — never the workflow engine.

## Quickstart

Prerequisites: Python 3.11+, Docker, [Ollama](https://ollama.com) running locally.

```bash
docker compose up -d

cp .env.example .env

pip install -e ".[test]"

alembic upgrade head

ollama pull qwen3.6

uvicorn app.main:app --reload
```

## API

```bash
# 1. start a workflow — runs plan → verify → human_review then pauses
curl -X POST localhost:8000/workflows \
  -H 'content-type: application/json' \
  -d '{"goal": "Draft a status report"}'

# 2. inspect status
curl localhost:8000/workflows/<workflow_id>

# 3. approve the pending human_review and resume to finalize
curl -X POST localhost:8000/approvals/<approval_id>/approve

# 4. confirm completion
curl localhost:8000/workflows/<workflow_id>
```

## Tests

```bash
pytest -q
```

The smoke test uses `FakeListChatModel` and an in-memory checkpointer with SQLite, so no Ollama or Postgres is required for `pytest`.

## Configuration

All settings via environment variables (see `.env.example`):

| Var | Default | Purpose |
|-----|---------|---------|
| `DB_URL` | `postgresql+psycopg://...` | SQLAlchemy URL for app tables |
| `CHECKPOINT_DB_URL` | same DB, libpq URL | LangGraph PostgresSaver |
| `LLM_PROVIDER` | `ollama` | `ollama` or `fake` |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server |
| `OLLAMA_MODEL` | `qwen3.6` | Ollama model tag |
| `ARTIFACT_DIR` | `./artifacts` | Local artifact store path |

## Out of Scope (this commit)

- Idempotent tool executor + tool registry
- Budget enforcement
- Saga/compensation, outbox/inbox, distributed locks
- Multi-agent planner/executor/verifier separation
- Vector store / long-term memory
- Object storage backends (S3/MinIO)
- Background workers
