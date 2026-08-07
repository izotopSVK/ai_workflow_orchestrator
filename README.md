# AI Workflow Orchestrator

Python-native, durable AI workflow system built on **LangGraph** (stateful graph
execution + checkpointing), **LangChain** (LLM/tool abstractions), **GitHub
Copilot** (enterprise LLM, SSO), and **PostgreSQL**.

Guiding principle: **the LLM is one node inside the graph — never the workflow
engine.** The graph is the engine, deterministic tools decide correctness, and
every side effect is a `Protocol` with a Fake, so the whole system runs in tests
with no external services.

## Two systems in this repo

- **MVP workflow API** — a generic durable workflow (`plan → verify →
  human_review → finalize`) exposed over FastAPI, with durable resume via
  LangGraph's Postgres checkpointer.
- **Self-learning dev orchestrator** — a decoupled pipeline that develops changes
  against a legacy **Yii 1.1** app targeting **PHP 8.4** with **SOLID**
  enforcement. It creates an isolated git worktree, loads the repo's
  `AGENTS.md`/skills, retrieves lessons from memory, plans and implements a diff,
  verifies it deterministically (php -l · Rector · PHPStan · PHP-CS-Fixer ·
  PHPUnit · SOLID), reflects and retries on failure, then distils lessons back
  into memory.

```
FastAPI ─▶ WorkflowService ─▶ LangGraph (plan → verify → human_review → finalize)
                                   ├─▶ GitHub Copilot (enterprise LLM, SSO)
                                   ├─▶ PostgresSaver (graph checkpoints)
                                   └─▶ SQLAlchemy ORM (workflows, approvals, events, artifacts)

dev orchestrator:
START → bootstrap → load_context → retrieve → analyze → plan → implement → verify
        (verify → reflect → implement  |  → human_review → finalize → learn → teardown)
```

## Quickstart

With [`just`](https://just.systems) the whole first setup is one command:

```bash
just init          # venv + deps + .env + Postgres + migrations
just login         # GitHub Copilot SSO (or set LLM_PROVIDER=fake in .env)
just run           # start the API at http://localhost:8000
```

`just` (bare) lists every recipe (`test`, `db-up`, `clean`, `fresh`, …). Prefer
manual steps? They're equivalent:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[test]"
cp .env.example .env
docker compose up -d
alembic upgrade head
uvicorn app.main:app --reload
```

```bash
curl -X POST localhost:8000/workflows \
  -H 'content-type: application/json' -d '{"goal": "Draft a status report"}'
```

Full setup (Copilot SSO auth, database, PHP toolchain) is in
**[docs/installation.md](docs/installation.md)**.

## Features

- **Enterprise LLM via GitHub Copilot**, SSO-compatible (OAuth device flow →
  short-lived Copilot token). [docs/auth_and_security.md](docs/auth_and_security.md)
- **Per-agent models** — each agent (`analyze`/`plan`/`implement`/`review_solid`/
  `reflect`) can run on its own model. [docs/configuration.md](docs/configuration.md)
- **Self-learning** — Reflexion loop + episodic/lesson memory (RAG).
  [docs/dev_orchestrator.md](docs/dev_orchestrator.md)
- **AGENTS.md standard + skills** loaded from the target repo.
  [docs/agents_and_skills.md](docs/agents_and_skills.md)
- **Context compression** via Headroom (+ RTK) to cut tokens & align the prompt
  cache. [docs/headroom_integration.md](docs/headroom_integration.md)
- **Secret/PII redaction** across logs, errors and tool output.
  [docs/logging_security.md](docs/logging_security.md)

## Documentation

The full docs live in **[`docs/`](docs/README.md)**:

| | |
|---|---|
| [Installation & setup](docs/installation.md) | [Usage](docs/usage.md) |
| [Configuration](docs/configuration.md) | [Architecture](docs/architecture.md) |
| [Dev orchestrator](docs/dev_orchestrator.md) | [Auth & security](docs/auth_and_security.md) |
| [AGENTS.md & skills](docs/agents_and_skills.md) | [Headroom + RTK](docs/headroom_integration.md) |

## Tests

```bash
pytest -q
```

Fakes for every side effect (LLM, git, PHP, memory, tokens) and an in-memory
SQLite checkpointer mean the suite needs no Copilot, PHP, git or Postgres.

## Status

Implemented: MVP workflow API, self-learning dev-orchestrator scaffold, Copilot
SSO auth, per-agent models, AGENTS.md/skills, Headroom compression + LLM cache,
secret/PII redaction. Notable stubs to wire for production: `PgVectorMemoryStore`
(embeddings-backed memory) and running against a concrete Yii 1.1 target repo.
See [docs/dev_orchestrator.md](docs/dev_orchestrator.md) for the productionization
checklist.
